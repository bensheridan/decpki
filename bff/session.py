"""JWT session tokens, refresh tokens, login challenges, and assertion verification."""
import base64
import hashlib
import json
import os
import secrets
import time
import uuid

from cryptography.exceptions import InvalidSignature
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

    # --- challenge store ---

    def create_challenge(self, did: str, credential_id: str, public_key_hex: str) -> str:
        raw = secrets.token_bytes(32)
        challenge_hex = raw.hex()
        now = int(time.time())
        self._challenges[challenge_hex] = {
            "did": did,
            "credential_id": credential_id,
            "public_key_hex": public_key_hex,
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

    def issue_session_token(self, did: str) -> tuple[str, int]:
        secret = os.environ.get("SESSION_SECRET", _SESSION_SECRET)
        if not secret:
            raise RuntimeError("SESSION_SECRET env var is required")
        lifetime = int(os.environ.get("SESSION_LIFETIME_SECONDS", str(_SESSION_LIFETIME)))
        now = int(time.time())
        exp = now + lifetime
        payload = {
            "sub": did,
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": exp,
            "type": "session",
        }
        token = jwt.encode(payload, secret, algorithm=_ALGORITHM)
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
        }
        return token, exp

    def consume_refresh_token(self, token: str) -> dict | None:
        """Return the entry without deleting (refresh keeps the token alive)."""
        return self._refresh_tokens.get(token)

    def revoke_refresh_token(self, token: str):
        self._refresh_tokens.pop(token, None)


def verify_assertion(
    authenticator_data_b64: str,
    client_data_json_b64: str,
    signature_b64: str,
    public_key_hex: str,
    expected_challenge_hex: str,
) -> bool:
    """Verify a WebAuthn assertion against a stored ed25519 public key.

    Verification data = authenticatorData || SHA-256(clientDataJSON) per W3C spec.
    expected_challenge_hex is the raw challenge bytes as hex (as stored in SessionStore).
    """
    try:
        auth_data = _b64url_decode(authenticator_data_b64)
        client_data_raw = _b64url_decode(client_data_json_b64)
        sig_bytes = _b64url_decode(signature_b64)

        client_data = json.loads(client_data_raw)
        if client_data.get("type") != "webauthn.get":
            return False

        # challenge in clientDataJSON is base64url of the raw challenge bytes
        recv_challenge_b64 = client_data.get("challenge", "")
        recv_challenge_hex = _b64url_decode(recv_challenge_b64).hex()
        if recv_challenge_hex != expected_challenge_hex:
            return False

        verification_data = auth_data + hashlib.sha256(client_data_raw).digest()

        pub_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        pub_key.verify(sig_bytes, verification_data)
        return True
    except (InvalidSignature, Exception):
        return False
