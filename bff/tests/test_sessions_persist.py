"""Cross-restart persistence tests for SqliteSessionStore (Feature 008)."""
import os
import time

import pytest

os.environ.setdefault("SESSION_SECRET", "testsecret-32-bytes-minimum-xxxx")

from session import SqliteSessionStore


# ── US1: Sessions survive restart ────────────────────────────────────────────

def test_refresh_token_survives_restart(tmp_path):
    path = str(tmp_path / "bff.db")
    s1 = SqliteSessionStore(path=path)
    token, exp = s1.issue_refresh_token("did:local:test")
    s1.close()

    s2 = SqliteSessionStore(path=path)
    entry = s2.consume_refresh_token(token)
    s2.close()

    assert entry is not None
    assert entry["did"] == "did:local:test"
    assert entry["expires_at"] == exp


def test_session_token_refresh_after_restart(tmp_path):
    path = str(tmp_path / "bff.db")
    s1 = SqliteSessionStore(path=path)
    token, _ = s1.issue_refresh_token("did:local:test")
    s1.close()

    s2 = SqliteSessionStore(path=path)
    jwt_str, exp = s2.issue_session_token("did:local:test", refresh_token_hex=token)
    s2.close()

    assert jwt_str is not None
    assert exp > int(time.time())


# ── US2: Revocations survive restart ─────────────────────────────────────────

def test_revocation_survives_restart(tmp_path):
    from jose import jwt as jose_jwt

    path = str(tmp_path / "bff.db")
    s1 = SqliteSessionStore(path=path)
    token, _ = s1.issue_refresh_token("did:local:test")
    session_jwt, _ = s1.issue_session_token("did:local:test", refresh_token_hex=token)
    payload = jose_jwt.decode(session_jwt, os.environ["SESSION_SECRET"], algorithms=["HS256"])
    jti = payload["jti"]
    session_id = token[:16]
    s1.revoke_session(session_id)
    s1.close()

    s2 = SqliteSessionStore(path=path)
    assert s2.is_jti_revoked(jti) is True
    s2.close()


def test_other_sessions_unaffected_after_revoke_restart(tmp_path):
    path = str(tmp_path / "bff.db")
    s1 = SqliteSessionStore(path=path)
    t1, _ = s1.issue_refresh_token("did:local:test")
    t2, _ = s1.issue_refresh_token("did:local:test")
    s1.issue_session_token("did:local:test", refresh_token_hex=t1)
    s1.revoke_session(t1[:16])
    s1.close()

    s2 = SqliteSessionStore(path=path)
    # t2 should still be consumable
    entry = s2.consume_refresh_token(t2)
    assert entry is not None
    assert entry["did"] == "did:local:test"
    # t1 should be gone
    assert s2.consume_refresh_token(t1) is None
    s2.close()


# ── US3: Challenge expiry respected after restart ─────────────────────────────

def test_valid_challenge_survives_restart(tmp_path):
    path = str(tmp_path / "bff.db")
    s1 = SqliteSessionStore(path=path)
    challenge_hex = s1.create_challenge(
        did="did:local:test",
        credential_id="cred-id",
        public_key_hex="aabbcc",
        algorithm="ed25519",
    )
    s1.close()

    s2 = SqliteSessionStore(path=path)
    entry = s2.consume_challenge(challenge_hex)
    s2.close()

    assert entry is not None
    assert entry["did"] == "did:local:test"
    assert entry["credential_id"] == "cred-id"


def test_expired_challenge_rejected_after_restart(tmp_path):
    path = str(tmp_path / "bff.db")
    s1 = SqliteSessionStore(path=path)
    challenge_hex = s1.create_challenge(
        did="did:local:test",
        credential_id="cred-id",
        public_key_hex="aabbcc",
    )
    # Force-expire the challenge in the DB
    s1._conn.execute(
        "UPDATE challenges SET expires_at = ? WHERE challenge_hex = ?",
        (int(time.time()) - 1, challenge_hex),
    )
    s1._conn.commit()
    s1.close()

    s2 = SqliteSessionStore(path=path)
    entry = s2.consume_challenge(challenge_hex)
    s2.close()

    # Expired challenge must be rejected (prune on startup or expiry check on consume)
    assert entry is None


# ── Polish: corrupt / missing store ──────────────────────────────────────────

def test_missing_store_starts_with_empty_state(tmp_path):
    path = str(tmp_path / "new.db")
    s = SqliteSessionStore(path=path)
    assert s.list_sessions("did:local:nobody") == []
    assert s.is_jti_revoked("any-jti") is False
    s.close()
