"""Tests for Feature 007: session list, revocation, and jti blocklist."""
import json
import os
import time
import unittest

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SESSION_SECRET", "testsecret-32-bytes-minimum-xxxx")
os.environ.setdefault("BUNDLE_PATH", "/tmp/nonexistent-bundle-for-tests.cbor")

from session import SessionStore


# ── SessionStore unit tests ───────────────────────────────────────────────────

class TestSessionStoreExtensions:
    def setup_method(self):
        self.store = SessionStore()

    def test_issue_refresh_token_populates_sessions_by_did(self):
        token, _ = self.store.issue_refresh_token("did:test:1")
        assert "did:test:1" in self.store._sessions_by_did
        assert token in self.store._sessions_by_did["did:test:1"]

    def test_revoke_refresh_token_removes_from_sessions_by_did(self):
        token, _ = self.store.issue_refresh_token("did:test:1")
        self.store.revoke_refresh_token(token)
        assert token not in self.store._sessions_by_did.get("did:test:1", set())

    def test_is_jti_revoked_returns_false_for_unknown(self):
        assert self.store.is_jti_revoked("nonexistent-jti") is False

    def test_is_jti_revoked_returns_true_after_revocation(self):
        token, _ = self.store.issue_refresh_token("did:test:1")
        session_token, _ = self.store.issue_session_token("did:test:1", refresh_token_hex=token)
        from jose import jwt
        payload = jwt.decode(session_token, os.environ["SESSION_SECRET"], algorithms=["HS256"])
        session_id = token[:16]
        self.store.revoke_session(session_id)
        assert self.store.is_jti_revoked(payload["jti"])

    def test_list_sessions_returns_active_entries(self):
        token, _ = self.store.issue_refresh_token("did:test:2")
        self.store.issue_session_token("did:test:2", refresh_token_hex=token)
        sessions = self.store.list_sessions("did:test:2")
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == token[:16]
        assert sessions[0]["did"] == "did:test:2"

    def test_list_sessions_skips_expired_entries(self):
        token, _ = self.store.issue_refresh_token("did:test:3")
        # Manually expire the entry
        self.store._refresh_tokens[token]["expires_at"] = int(time.time()) - 1
        sessions = self.store.list_sessions("did:test:3")
        assert sessions == []

    def test_list_sessions_returns_empty_for_unknown_did(self):
        assert self.store.list_sessions("did:unknown") == []

    def test_revoke_session_returns_false_for_unknown(self):
        found, token_hex = self.store.revoke_session("0000000000000000")
        assert found is False
        assert token_hex is None

    def test_revoke_session_idempotent_second_call(self):
        token, _ = self.store.issue_refresh_token("did:test:4")
        session_id = token[:16]
        found1, _ = self.store.revoke_session(session_id)
        found2, _ = self.store.revoke_session(session_id)
        assert found1 is True
        assert found2 is False

    def test_issue_session_token_updates_last_jti(self):
        token, _ = self.store.issue_refresh_token("did:test:5")
        assert self.store._refresh_tokens[token]["last_jti"] == ""
        self.store.issue_session_token("did:test:5", refresh_token_hex=token)
        assert self.store._refresh_tokens[token]["last_jti"] != ""

    def test_multiple_sessions_for_same_did(self):
        t1, _ = self.store.issue_refresh_token("did:test:6")
        t2, _ = self.store.issue_refresh_token("did:test:6")
        sessions = self.store.list_sessions("did:test:6")
        assert len(sessions) == 2


# ── Integration tests via FastAPI TestClient ──────────────────────────────────

@pytest.fixture()
def client_with_session():
    """Return (client, session_token, refresh_token, did) for a fresh in-memory store."""
    from main import app
    import main as main_module

    did = "did:local:test-sessions-007"

    with TestClient(app) as c:
        # lifespan has run — now inject a fresh store and populate it
        store = SessionStore()
        main_module._session_store = store

        refresh_token, _ = store.issue_refresh_token(did)
        session_token, _ = store.issue_session_token(did, refresh_token_hex=refresh_token)

        yield c, session_token, refresh_token, did


class TestSessionsEndpoint:
    def test_get_sessions_requires_auth(self, client_with_session):
        client, _, refresh_token, _ = client_with_session
        r = client.request(
            "GET", "/api/sessions",
            data=json.dumps({"refresh_token": refresh_token}),
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 401

    def test_get_sessions_returns_list(self, client_with_session):
        client, session_token, refresh_token, did = client_with_session
        r = client.request(
            "GET", "/api/sessions",
            data=json.dumps({"refresh_token": refresh_token}),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {session_token}",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert "sessions" in body
        assert len(body["sessions"]) == 1
        assert body["sessions"][0]["did"] == did
        assert body["sessions"][0]["is_current"] is True

    def test_delete_session_returns_ok(self, client_with_session):
        client, session_token, refresh_token, did = client_with_session
        session_id = refresh_token[:16]
        r = client.delete(
            f"/api/sessions/{session_id}",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["self_revoked"] is True

    def test_delete_session_not_found(self, client_with_session):
        client, session_token, _, _ = client_with_session
        r = client.delete(
            "/api/sessions/0000000000000000",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        assert r.status_code == 404

    def test_revoked_session_token_rejected_on_api_me(self, client_with_session):
        client, session_token, refresh_token, _ = client_with_session
        session_id = refresh_token[:16]
        # Revoke the session
        client.delete(
            f"/api/sessions/{session_id}",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        # The same token should now be rejected
        r = client.get("/api/me", headers={"Authorization": f"Bearer {session_token}"})
        assert r.status_code == 401
        assert "revoked" in r.json()["detail"].lower()

    def test_revoked_session_token_rejected_on_login_verify(self, client_with_session):
        client, session_token, refresh_token, _ = client_with_session
        session_id = refresh_token[:16]
        client.delete(
            f"/api/sessions/{session_id}",
            headers={"Authorization": f"Bearer {session_token}"},
        )
        r = client.get("/api/login/verify", headers={"Authorization": f"Bearer {session_token}"})
        # /login/verify path is /login/verify
        r2 = client.get("/login/verify", headers={"Authorization": f"Bearer {session_token}"})
        assert r2.status_code == 401
        assert "revoked" in r2.json()["detail"].lower()
