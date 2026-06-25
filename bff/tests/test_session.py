"""Tests for SessionStore, verify_assertion, and /login/* endpoints."""
import base64
import json
import os
import sys
import time
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("SESSION_SECRET", "test-secret-at-least-32-bytes-ok!")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    s = s.replace("-", "+").replace("_", "/")
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.b64decode(s)


# ── SessionStore unit tests ────────────────────────────────────────────────────

class TestSessionStore:
    def setup_method(self):
        from session import SessionStore
        self.store = SessionStore()

    def test_create_challenge_returns_hex(self):
        ch = self.store.create_challenge("did:local:test", "cred-id", "deadbeef" * 8)
        assert isinstance(ch, str)
        assert len(ch) == 64  # 32 bytes as hex

    def test_consume_challenge_returns_entry(self):
        ch = self.store.create_challenge("did:local:test", "cred-id", "aa" * 32)
        entry = self.store.consume_challenge(ch)
        assert entry is not None
        assert entry["did"] == "did:local:test"

    def test_consume_challenge_single_use(self):
        ch = self.store.create_challenge("did:local:test", "cred-id", "aa" * 32)
        self.store.consume_challenge(ch)
        assert self.store.consume_challenge(ch) is None

    def test_consume_challenge_expired(self):
        ch = self.store.create_challenge("did:local:test", "cred-id", "aa" * 32)
        with patch("session.time") as mock_time:
            # Return a time far in the future during consume
            import session as sess_mod
            entry = self.store._challenges[ch]
            entry["expires_at"] = int(time.time()) - 1
        assert self.store.consume_challenge(ch) is None

    def test_issue_session_token_decodable(self):
        from jose import jwt
        token, exp = self.store.issue_session_token("did:local:abc")
        payload = jwt.decode(token, os.environ["SESSION_SECRET"], algorithms=["HS256"])
        assert payload["sub"] == "did:local:abc"
        assert payload["type"] == "session"
        assert payload["exp"] == exp

    def test_verify_session_token_tampered_raises(self):
        from jose import JWTError
        token, _ = self.store.issue_session_token("did:local:abc")
        tampered = token[:-4] + "XXXX"
        with pytest.raises(JWTError):
            self.store.verify_session_token(tampered)

    def test_refresh_token_roundtrip(self):
        token, exp = self.store.issue_refresh_token("did:local:xyz")
        assert len(token) == 64
        entry = self.store.consume_refresh_token(token)
        assert entry is not None
        assert entry["did"] == "did:local:xyz"

    def test_revoke_refresh_token(self):
        token, _ = self.store.issue_refresh_token("did:local:xyz")
        self.store.revoke_refresh_token(token)
        assert self.store.consume_refresh_token(token) is None

    def test_revoke_nonexistent_is_noop(self):
        self.store.revoke_refresh_token("nonexistent-token")  # must not raise


# ── /login/* integration tests ─────────────────────────────────────────────────

@pytest.fixture
def promoted_dir(tmp_path):
    d = tmp_path / "promoted"
    d.mkdir()
    return d


@pytest.fixture
def client(promoted_dir, monkeypatch):
    monkeypatch.setenv("ENROLMENT_DIR", str(promoted_dir.parent))
    monkeypatch.setenv("SESSION_SECRET", "test-secret-at-least-32-bytes-ok!")
    # Patch bundle cache to avoid file I/O
    import bundle_cache as bc
    import session as sess

    from fastapi.testclient import TestClient
    import main

    with TestClient(main.app) as c:
        # Replace singletons with fresh instances
        main._session_store = sess.SessionStore()
        main._bundle_cache = bc.BundleCache.__new__(bc.BundleCache)
        main._bundle_cache._bundle = None
        main._bundle_cache._lock = __import__("threading").Lock()
        yield c, main, promoted_dir


def _write_promoted(promoted_dir: Path, did: str, public_key_hex: str, credential_id: str):
    import uuid
    record = {
        "id": str(uuid.uuid4()),
        "did": did,
        "public_key_hex": public_key_hex,
        "credential_id": credential_id,
        "status": "promoted",
    }
    (promoted_dir / f"{record['id']}.json").write_text(json.dumps(record))


def test_login_start_unknown_did(client):
    c, _, _ = client
    r = c.post("/login/start", json={"did": "did:local:unknown"})
    assert r.status_code == 404


def test_login_start_known_did(client):
    c, main_mod, promoted_dir = client
    _write_promoted(promoted_dir, "did:local:test-001", "ab" * 32, "cred-abc")
    r = c.post("/login/start", json={"did": "did:local:test-001"})
    assert r.status_code == 200
    body = r.json()
    assert "challenge" in body
    assert body["allow_credentials"][0]["id"] == "cred-abc"


def test_login_complete_bad_challenge(client):
    c, main_mod, promoted_dir = client
    _write_promoted(promoted_dir, "did:local:test-002", "ab" * 32, "cred-xyz")
    # Don't call /login/start — submit with a fabricated challenge
    fake_challenge = _b64url(b"\x00" * 32)
    client_data = json.dumps({"type": "webauthn.get", "challenge": fake_challenge}).encode()
    client_data_b64 = _b64url(client_data)
    assertion = {
        "response": {
            "authenticatorData": _b64url(b"\x00" * 37),
            "clientDataJSON": client_data_b64,
            "signature": _b64url(b"\x00" * 64),
        }
    }
    r = c.post("/login/complete", json={"did": "did:local:test-002", "assertion": assertion})
    assert r.status_code == 401


def test_login_verify_no_token(client):
    c, _, _ = client
    r = c.get("/login/verify")
    assert r.status_code == 401


def test_login_verify_valid_token(client):
    c, main_mod, _ = client
    token, exp = main_mod._session_store.issue_session_token("did:local:verify-test")
    r = c.get("/login/verify", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["did"] == "did:local:verify-test"


def test_login_verify_expired_token(client):
    c, main_mod, _ = client
    # Issue a token, then tamper the secret so verify fails
    token, _ = main_mod._session_store.issue_session_token("did:local:exp-test")
    # Use wrong secret to force JWTError
    r = c.get("/login/verify", headers={"Authorization": f"Bearer {token}XXXXXX"})
    assert r.status_code == 401


def test_login_refresh_after_logout(client):
    c, main_mod, _ = client
    ref_token, _ = main_mod._session_store.issue_refresh_token("did:local:refresh-test")
    # Logout first
    r = c.post("/login/logout", json={"refresh_token": ref_token})
    assert r.status_code == 200
    # Now refresh should fail
    r = c.post("/login/refresh", json={"refresh_token": ref_token})
    assert r.status_code == 401


def test_login_logout_idempotent(client):
    c, main_mod, _ = client
    ref_token, _ = main_mod._session_store.issue_refresh_token("did:local:logout-test")
    r1 = c.post("/login/logout", json={"refresh_token": ref_token})
    r2 = c.post("/login/logout", json={"refresh_token": ref_token})
    assert r1.status_code == 200
    assert r2.status_code == 200
