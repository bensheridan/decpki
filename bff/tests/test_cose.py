"""Unit tests for COSE key extraction."""
import struct

import cbor2
import pytest

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from cose import extract_ed25519_pubkey


def _make_auth_data(cose_key: dict, credential_id: bytes = b"\x01" * 16) -> bytes:
    rp_id_hash = b"\x00" * 32
    flags = 0x41  # UP + AT
    sign_count = struct.pack(">I", 0)
    aaguid = b"\x00" * 16
    cred_id_len = struct.pack(">H", len(credential_id))
    cose_bytes = cbor2.dumps(cose_key)
    return rp_id_hash + bytes([flags]) + sign_count + aaguid + cred_id_len + credential_id + cose_bytes


def _make_attestation(cose_key: dict) -> bytes:
    auth_data = _make_auth_data(cose_key)
    return cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})


def _ed25519_cose_key(x: bytes = b"\xab" * 32) -> dict:
    return {1: 1, 3: -8, -1: 6, -2: x}


def test_valid_ed25519_returns_pubkey():
    pubkey_bytes = bytes(range(32))
    att = _make_attestation(_ed25519_cose_key(pubkey_bytes))
    result = extract_ed25519_pubkey(att)
    assert result == pubkey_bytes


def test_p256_raises_value_error():
    p256_key = {1: 2, 3: -7, -1: 1, -2: b"\x00" * 32, -3: b"\x00" * 32}
    att = _make_attestation(p256_key)
    with pytest.raises(ValueError, match="ed25519"):
        extract_ed25519_pubkey(att)


def test_malformed_cbor_raises():
    with pytest.raises(ValueError, match="CBOR"):
        extract_ed25519_pubkey(b"\xff\xfe\xfd")


def test_missing_auth_data_raises():
    att = cbor2.dumps({"fmt": "none", "attStmt": {}})
    with pytest.raises(ValueError, match="authData"):
        extract_ed25519_pubkey(att)


def test_base64url_string_input():
    import base64
    pubkey_bytes = b"\x42" * 32
    att = _make_attestation(_ed25519_cose_key(pubkey_bytes))
    att_b64 = base64.urlsafe_b64encode(att).rstrip(b"=").decode()
    result = extract_ed25519_pubkey(att_b64)
    assert result == pubkey_bytes
