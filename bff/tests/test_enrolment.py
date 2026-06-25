"""Integration tests for the FIDO2 enrolment BFF endpoints."""
import base64
import json
import struct
import tempfile
import time
from pathlib import Path

import cbor2
import pytest
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _make_cose_ed25519_key(x: bytes = b"\xab" * 32) -> dict:
    return {1: 1, 3: -8, -1: 6, -2: x}


def _make_auth_data(cose_key: dict, credential_id: bytes = b"\x01" * 16) -> bytes:
    rp_id_hash = b"\x00" * 32
    flags = 0x41
    sign_count = struct.pack(">I", 0)
    aaguid = b"\x00" * 16
    cred_id_len = struct.pack(">H", len(credential_id))
    cose_bytes = cbor2.dumps(cose_key)
    return rp_id_hash + bytes([flags]) + sign_count + aaguid + cred_id_len + credential_id + cose_bytes


def _make_attestation_b64(cose_key: dict, credential_id: bytes = b"\x01" * 16) -> str:
    auth_data = _make_auth_data(cose_key, credential_id)
    att_obj = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
    return base64.urlsafe_b64encode(att_obj).rstrip(b"=").decode()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@pytest.fixture
def client(tmp_path):
    os.environ["ENROLMENT_DIR"] = str(tmp_path / "enrolments")
    os.environ["ENROLMENT_TTL_SECONDS"] = "3600"

    import importlib
    import enrolment as enrolment_mod
    import main as main_mod

    enrolment_mod._DEFAULT_DIR = tmp_path / "enrolments"
    main_mod._store = None
    main_mod._challenges.clear()
    main_mod._nonces.clear()

    from enrolment import EnrolmentStore
    main_mod._store = EnrolmentStore(enrolment_dir=tmp_path / "enrolments", threshold=2)

    from fastapi.testclient import TestClient
    return TestClient(main_mod.app)


def _make_credential(client, pubkey: bytes = b"\xab" * 32, cred_id: bytes = b"\x01" * 16):
    start_resp = client.post("/enrolment/start")
    assert start_resp.status_code == 200
    start = start_resp.json()

    client_data = json.dumps({
        "type": "webauthn.create",
        "challenge": start["challenge"],
        "origin": "http://localhost:3000",
    }).encode()
    client_data_b64 = _b64url(client_data)
    att_b64 = _make_attestation_b64(_make_cose_ed25519_key(pubkey), cred_id)

    return start["pending_did"], {
        "id": _b64url(cred_id),
        "rawId": _b64url(cred_id),
        "type": "public-key",
        "response": {
            "clientDataJSON": client_data_b64,
            "attestationObject": att_b64,
        },
    }


def test_start_returns_options(client):
    resp = client.post("/enrolment/start")
    assert resp.status_code == 200
    data = resp.json()
    assert data["request_type"] == "new"
    assert data["pending_did"].startswith("did:local:")
    assert "challenge" in data
    assert data["pubKeyCredParams"] == [{"type": "public-key", "alg": -8}]


def test_submit_new_registration(client):
    pending_did, credential = _make_credential(client)
    resp = client.post("/enrolment/submit", json={
        "pending_did": pending_did,
        "credential": credential,
        "ownership_assertion": None,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["did"] == pending_did
    assert data["status"] == "pending"
    assert data["signatures_collected"] == 0
    assert data["threshold"] == 2


def test_get_status(client):
    pending_did, credential = _make_credential(client)
    submit = client.post("/enrolment/submit", json={
        "pending_did": pending_did,
        "credential": credential,
        "ownership_assertion": None,
    })
    assert submit.status_code == 201
    request_id = submit.json()["request_id"]

    resp = client.get(f"/enrolment/{request_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_duplicate_credential_rejected(client):
    cred_id = b"\x42" * 16
    pending_did, credential = _make_credential(client, cred_id=cred_id)
    client.post("/enrolment/submit", json={
        "pending_did": pending_did,
        "credential": credential,
        "ownership_assertion": None,
    })

    # Second attempt with the same credential_id but fresh challenge
    pending_did2, credential2 = _make_credential(client, cred_id=cred_id)
    resp = client.post("/enrolment/submit", json={
        "pending_did": pending_did2,
        "credential": credential2,
        "ownership_assertion": None,
    })
    assert resp.status_code == 409


def test_wrong_algorithm_rejected(client):
    start_resp = client.post("/enrolment/start")
    start = start_resp.json()

    p256_key = {1: 2, 3: -7, -1: 1, -2: b"\x00" * 32, -3: b"\x00" * 32}
    att_b64 = _make_attestation_b64(p256_key)
    client_data = json.dumps({
        "type": "webauthn.create",
        "challenge": start["challenge"],
        "origin": "http://localhost:3000",
    }).encode()

    resp = client.post("/enrolment/submit", json={
        "pending_did": start["pending_did"],
        "credential": {
            "id": _b64url(b"\x99" * 16),
            "rawId": _b64url(b"\x99" * 16),
            "type": "public-key",
            "response": {
                "clientDataJSON": _b64url(client_data),
                "attestationObject": att_b64,
            },
        },
        "ownership_assertion": None,
    })
    assert resp.status_code == 422
    assert "ed25519" in resp.json()["detail"]


def test_list_requests(client):
    _did, cred = _make_credential(client, cred_id=b"\xaa" * 16)
    client.post("/enrolment/submit", json={
        "pending_did": _did,
        "credential": cred,
        "ownership_assertion": None,
    })
    resp = client.get("/enrolment/")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
