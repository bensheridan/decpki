"""Tests for GET /api/me protected resource endpoint."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("SESSION_SECRET", "test-secret-at-least-32-bytes-ok!")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "test-secret-at-least-32-bytes-ok!")
    import bundle_cache as bc
    import session as sess
    from fastapi.testclient import TestClient
    import main

    with TestClient(main.app) as c:
        main._session_store = sess.SessionStore()
        main._bundle_cache = bc.BundleCache.__new__(bc.BundleCache)
        main._bundle_cache._bundle = None
        main._bundle_cache._lock = __import__("threading").Lock()
        yield c, main


def test_api_me_valid_token(client):
    c, main_mod = client
    token, exp = main_mod._session_store.issue_session_token("did:local:me-test")
    r = c.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["did"] == "did:local:me-test"
    assert body["expires_at"] == exp
    assert body["message"] == "Hello, did:local:me-test"
    assert "issued_at" in body


def test_api_me_missing_header(client):
    c, _ = client
    r = c.get("/api/me")
    assert r.status_code == 401
    assert "Authorization" in r.json()["detail"]


def test_api_me_no_bearer_prefix(client):
    c, main_mod = client
    token, _ = main_mod._session_store.issue_session_token("did:local:test")
    r = c.get("/api/me", headers={"Authorization": token})
    assert r.status_code == 401


def test_api_me_tampered_token(client):
    c, main_mod = client
    token, _ = main_mod._session_store.issue_session_token("did:local:test")
    tampered = token[:-4] + "XXXX"
    r = c.get("/api/me", headers={"Authorization": f"Bearer {tampered}"})
    assert r.status_code == 401
