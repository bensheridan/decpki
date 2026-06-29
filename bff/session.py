"""JWT session tokens, refresh tokens, login challenges, and assertion verification."""
import base64
import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ec import ECDSA, EllipticCurvePublicNumbers, SECP256R1
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from jose import jwt, JWTError  # noqa: F401 (re-export for callers)


_SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
_SESSION_LIFETIME = int(os.environ.get("SESSION_LIFETIME_SECONDS", "900"))
_REFRESH_LIFETIME = int(os.environ.get("REFRESH_LIFETIME_SECONDS", "604800"))
_ALGORITHM = "HS256"


def _b64url_decode(s: str) -> bytes:
    s = s.replace("-", "+").replace("_", "/")
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.b64decode(s)


class SessionStore:
    def __init__(self):
        self._challenges: dict[str, dict] = {}
        self._refresh_tokens: dict[str, dict] = {}
        self._jti_blocklist: set[str] = set()
        self._sessions_by_did: dict[str, set[str]] = {}

    # --- challenge store ---

    def create_challenge(self, did: str, credential_id: str, public_key_hex: str, algorithm: str = "ed25519") -> str:
        raw = secrets.token_bytes(32)
        challenge_hex = raw.hex()
        now = int(time.time())
        self._challenges[challenge_hex] = {
            "did": did,
            "credential_id": credential_id,
            "public_key_hex": public_key_hex,
            "algorithm": algorithm,
            "issued_at": now,
            "expires_at": now + 60,
        }
        return challenge_hex

    def consume_challenge(self, challenge_hex: str) -> dict | None:
        entry = self._challenges.pop(challenge_hex, None)
        if entry is None:
            return None
        if int(time.time()) > entry["expires_at"]:
            return None
        return entry

    # --- session tokens ---

    def issue_session_token(self, did: str, refresh_token_hex: str | None = None) -> tuple[str, int]:
        secret = os.environ.get("SESSION_SECRET", _SESSION_SECRET)
        if not secret:
            raise RuntimeError("SESSION_SECRET env var is required")
        lifetime = int(os.environ.get("SESSION_LIFETIME_SECONDS", str(_SESSION_LIFETIME)))
        now = int(time.time())
        exp = now + lifetime
        jti = str(uuid.uuid4())
        payload = {
            "sub": did,
            "jti": jti,
            "iat": now,
            "exp": exp,
            "type": "session",
        }
        token = jwt.encode(payload, secret, algorithm=_ALGORITHM)
        if refresh_token_hex and refresh_token_hex in self._refresh_tokens:
            self._refresh_tokens[refresh_token_hex]["last_jti"] = jti
        return token, exp

    def verify_session_token(self, token: str) -> dict:
        secret = os.environ.get("SESSION_SECRET", _SESSION_SECRET)
        return jwt.decode(token, secret, algorithms=[_ALGORITHM])

    # --- refresh tokens ---

    def issue_refresh_token(self, did: str) -> tuple[str, int]:
        raw = secrets.token_bytes(32)
        token = raw.hex()
        now = int(time.time())
        lifetime = int(os.environ.get("REFRESH_LIFETIME_SECONDS", str(_REFRESH_LIFETIME)))
        exp = now + lifetime
        self._refresh_tokens[token] = {
            "did": did,
            "issued_at": now,
            "expires_at": exp,
            "last_jti": "",
        }
        if did not in self._sessions_by_did:
            self._sessions_by_did[did] = set()
        self._sessions_by_did[did].add(token)
        return token, exp

    def consume_refresh_token(self, token: str) -> dict | None:
        """Return the entry without deleting (refresh keeps the token alive)."""
        return self._refresh_tokens.get(token)

    def revoke_refresh_token(self, token: str):
        entry = self._refresh_tokens.pop(token, None)
        if entry:
            did = entry.get("did", "")
            if did in self._sessions_by_did:
                self._sessions_by_did[did].discard(token)

    # --- jti blocklist ---

    def is_jti_revoked(self, jti: str) -> bool:
        return jti in self._jti_blocklist

    # --- session listing and revocation ---

    def list_sessions(self, did: str) -> list[dict]:
        now = int(time.time())
        result = []
        for token_hex in list(self._sessions_by_did.get(did, set())):
            entry = self._refresh_tokens.get(token_hex)
            if entry is None or now > entry["expires_at"]:
                self._sessions_by_did.get(did, set()).discard(token_hex)
                continue
            result.append({
                "session_id": token_hex[:16],
                "did": did,
                "issued_at": entry["issued_at"],
                "expires_at": entry["expires_at"],
                "last_jti": entry.get("last_jti", ""),
            })
        return result

    def revoke_session(self, session_id: str) -> tuple[bool, str | None]:
        for token_hex, entry in list(self._refresh_tokens.items()):
            if token_hex[:16] == session_id:
                last_jti = entry.get("last_jti", "")
                if last_jti:
                    self._jti_blocklist.add(last_jti)
                self.revoke_refresh_token(token_hex)
                return True, token_hex
        return False, None


class SqliteSessionStore:
    """Drop-in replacement for SessionStore backed by SQLite for restart-safe persistence."""

    def __init__(self, path: str | None = None):
        self._path = path or os.environ.get("BFF_STORE_PATH", "/tmp/decpki-bff.db")
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
        self._init_schema()
        self._prune_expired()
        print(f"[session-store] using SQLite at {self._path}", flush=True)

    def close(self):
        self._conn.close()

    # ── schema ────────────────────────────────────────────────────────────────

    def _init_schema(self):
        with self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS challenges (
                    challenge_hex  TEXT PRIMARY KEY,
                    did            TEXT NOT NULL,
                    credential_id  TEXT NOT NULL,
                    public_key_hex TEXT NOT NULL,
                    algorithm      TEXT NOT NULL DEFAULT 'ed25519',
                    issued_at      INTEGER NOT NULL,
                    expires_at     INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    token_hex  TEXT PRIMARY KEY,
                    did        TEXT NOT NULL,
                    issued_at  INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    last_jti   TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_rt_did ON refresh_tokens(did);
                CREATE TABLE IF NOT EXISTS jti_blocklist (
                    jti          TEXT PRIMARY KEY,
                    added_at     INTEGER NOT NULL,
                    original_exp INTEGER NOT NULL
                );
            """)

    def _prune_expired(self):
        now = int(time.time())
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM challenges WHERE expires_at < ?", (now,))
            self._conn.execute("DELETE FROM refresh_tokens WHERE expires_at < ?", (now,))
            self._conn.execute("DELETE FROM jti_blocklist WHERE original_exp < ?", (now,))

    # ── challenge store ───────────────────────────────────────────────────────

    def create_challenge(self, did: str, credential_id: str, public_key_hex: str, algorithm: str = "ed25519") -> str:
        raw = secrets.token_bytes(32)
        challenge_hex = raw.hex()
        now = int(time.time())
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO challenges VALUES (?,?,?,?,?,?,?)",
                (challenge_hex, did, credential_id, public_key_hex, algorithm, now, now + 60),
            )
        return challenge_hex

    def consume_challenge(self, challenge_hex: str) -> dict | None:
        now = int(time.time())
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT did, credential_id, public_key_hex, algorithm, issued_at, expires_at "
                "FROM challenges WHERE challenge_hex = ?",
                (challenge_hex,),
            ).fetchone()
            if row is None:
                return None
            self._conn.execute("DELETE FROM challenges WHERE challenge_hex = ?", (challenge_hex,))
        did, credential_id, public_key_hex, algorithm, issued_at, expires_at = row
        if now > expires_at:
            return None
        return {
            "did": did,
            "credential_id": credential_id,
            "public_key_hex": public_key_hex,
            "algorithm": algorithm,
            "issued_at": issued_at,
            "expires_at": expires_at,
        }

    # ── session tokens ────────────────────────────────────────────────────────

    def issue_session_token(self, did: str, refresh_token_hex: str | None = None) -> tuple[str, int]:
        secret = os.environ.get("SESSION_SECRET", _SESSION_SECRET)
        if not secret:
            raise RuntimeError("SESSION_SECRET env var is required")
        lifetime = int(os.environ.get("SESSION_LIFETIME_SECONDS", str(_SESSION_LIFETIME)))
        now = int(time.time())
        exp = now + lifetime
        jti = str(uuid.uuid4())
        payload = {"sub": did, "jti": jti, "iat": now, "exp": exp, "type": "session"}
        token = jwt.encode(payload, secret, algorithm=_ALGORITHM)
        if refresh_token_hex:
            with self._lock, self._conn:
                self._conn.execute(
                    "UPDATE refresh_tokens SET last_jti = ? WHERE token_hex = ?",
                    (jti, refresh_token_hex),
                )
        return token, exp

    def verify_session_token(self, token: str) -> dict:
        secret = os.environ.get("SESSION_SECRET", _SESSION_SECRET)
        return jwt.decode(token, secret, algorithms=[_ALGORITHM])

    # ── refresh tokens ────────────────────────────────────────────────────────

    def issue_refresh_token(self, did: str) -> tuple[str, int]:
        raw = secrets.token_bytes(32)
        token = raw.hex()
        now = int(time.time())
        lifetime = int(os.environ.get("REFRESH_LIFETIME_SECONDS", str(_REFRESH_LIFETIME)))
        exp = now + lifetime
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO refresh_tokens VALUES (?,?,?,?,?)",
                (token, did, now, exp, ""),
            )
        return token, exp

    def consume_refresh_token(self, token: str) -> dict | None:
        now = int(time.time())
        with self._lock:
            row = self._conn.execute(
                "SELECT did, issued_at, expires_at, last_jti FROM refresh_tokens WHERE token_hex = ?",
                (token,),
            ).fetchone()
        if row is None:
            return None
        did, issued_at, expires_at, last_jti = row
        if now > expires_at:
            return None
        return {"did": did, "issued_at": issued_at, "expires_at": expires_at, "last_jti": last_jti}

    def revoke_refresh_token(self, token: str):
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM refresh_tokens WHERE token_hex = ?", (token,))

    # ── jti blocklist ─────────────────────────────────────────────────────────

    def is_jti_revoked(self, jti: str) -> bool:
        now = int(time.time())
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM jti_blocklist WHERE jti = ? AND original_exp > ?", (jti, now)
            ).fetchone()
        return row is not None

    # ── session listing and revocation ────────────────────────────────────────

    def list_sessions(self, did: str) -> list[dict]:
        now = int(time.time())
        with self._lock:
            rows = self._conn.execute(
                "SELECT token_hex, issued_at, expires_at, last_jti FROM refresh_tokens "
                "WHERE did = ? AND expires_at > ?",
                (did, now),
            ).fetchall()
        return [
            {
                "session_id": r[0][:16],
                "did": did,
                "issued_at": r[1],
                "expires_at": r[2],
                "last_jti": r[3],
            }
            for r in rows
        ]

    def revoke_session(self, session_id: str) -> tuple[bool, str | None]:
        now = int(time.time())
        lifetime = int(os.environ.get("SESSION_LIFETIME_SECONDS", str(_SESSION_LIFETIME)))
        with self._lock:
            rows = self._conn.execute(
                "SELECT token_hex, last_jti FROM refresh_tokens"
            ).fetchall()
        for token_hex, last_jti in rows:
            if token_hex[:16] == session_id:
                if last_jti:
                    with self._lock, self._conn:
                        self._conn.execute(
                            "INSERT OR IGNORE INTO jti_blocklist VALUES (?,?,?)",
                            (last_jti, now, now + lifetime),
                        )
                self.revoke_refresh_token(token_hex)
                return True, token_hex
        return False, None


def verify_assertion(
    authenticator_data_b64: str,
    client_data_json_b64: str,
    signature_b64: str,
    public_key_hex: str,
    expected_challenge_hex: str,
    algorithm: str = "ed25519",
) -> bool:
    """Verify a WebAuthn assertion against a stored public key.

    Supports algorithm="ed25519" and algorithm="es256".
    Verification data = authenticatorData || SHA-256(clientDataJSON) per W3C spec.
    """
    try:
        auth_data = _b64url_decode(authenticator_data_b64)
        client_data_raw = _b64url_decode(client_data_json_b64)
        sig_bytes = _b64url_decode(signature_b64)

        client_data = json.loads(client_data_raw)
        if client_data.get("type") != "webauthn.get":
            return False

        recv_challenge_b64 = client_data.get("challenge", "")
        recv_challenge_hex = _b64url_decode(recv_challenge_b64).hex()
        if recv_challenge_hex != expected_challenge_hex:
            return False

        verification_data = auth_data + hashlib.sha256(client_data_raw).digest()

        if algorithm == "es256":
            pub_bytes = bytes.fromhex(public_key_hex)  # 65-byte uncompressed point
            x = int.from_bytes(pub_bytes[1:33], "big")
            y = int.from_bytes(pub_bytes[33:65], "big")
            pub_key = EllipticCurvePublicNumbers(x=x, y=y, curve=SECP256R1()).public_key()
            pub_key.verify(sig_bytes, verification_data, ECDSA(hashes.SHA256()))
        else:
            pub_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
            pub_key.verify(sig_bytes, verification_data)

        return True
    except (InvalidSignature, Exception):
        return False
