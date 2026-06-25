"""COSE key extraction from WebAuthn attestation objects.

Only ed25519 (COSE algorithm -8, OKP key type, Ed25519 curve) is accepted.
All other algorithms raise ValueError.
"""
import base64
import struct

import cbor2


_COSE_ALG_EDDSA = -8
_COSE_KTY_OKP = 1
_COSE_CRV_ED25519 = 6

_COSE_KEY_KTY = 1
_COSE_KEY_ALG = 3
_COSE_KEY_CRV = -1
_COSE_KEY_X = -2

_AUTHDATA_MIN_LEN = 37
_AUTHDATA_FLAG_AT = 0x40


def _b64url_decode(s: str) -> bytes:
    s = s.replace("-", "+").replace("_", "/")
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.b64decode(s)


def extract_ed25519_pubkey(attestation_object: bytes | str) -> bytes:
    """Extract the raw 32-byte ed25519 public key from a WebAuthn attestation object.

    Args:
        attestation_object: Raw bytes or base64url-encoded attestation object.

    Returns:
        32-byte raw ed25519 public key.

    Raises:
        ValueError: If the credential is not ed25519 or the attestation object is malformed.
    """
    if isinstance(attestation_object, str):
        attestation_object = _b64url_decode(attestation_object)

    try:
        att = cbor2.loads(attestation_object)
    except Exception as e:
        raise ValueError(f"Failed to decode CBOR attestation object: {e}") from e

    if not isinstance(att, dict):
        raise ValueError(f"Failed to decode CBOR attestation object: expected map, got {type(att).__name__}")

    auth_data = att.get("authData")
    if auth_data is None:
        raise ValueError("attestationObject missing 'authData' field")

    auth_data = bytes(auth_data)

    if len(auth_data) < _AUTHDATA_MIN_LEN:
        raise ValueError(f"authData too short: {len(auth_data)} bytes")

    flags = auth_data[32]
    if not (flags & _AUTHDATA_FLAG_AT):
        raise ValueError("authData AT flag not set — no attested credential data present")

    offset = 37
    if len(auth_data) < offset + 18:
        raise ValueError("authData truncated in attested credential data header")

    offset += 16  # skip aaguid
    cred_id_len = struct.unpack(">H", auth_data[offset:offset + 2])[0]
    offset += 2
    offset += cred_id_len  # skip credential ID

    cose_key_bytes = auth_data[offset:]
    if not cose_key_bytes:
        raise ValueError("authData contains no COSE public key bytes")

    try:
        cose_key = cbor2.loads(cose_key_bytes)
    except Exception as e:
        raise ValueError(f"Failed to decode COSE key: {e}") from e

    alg = cose_key.get(_COSE_KEY_ALG)
    if alg != _COSE_ALG_EDDSA:
        raise ValueError(
            f"Only ed25519 credentials (COSE alg -8) are accepted. Got alg: {alg}"
        )

    kty = cose_key.get(_COSE_KEY_KTY)
    if kty != _COSE_KTY_OKP:
        raise ValueError(f"Expected OKP key type (1), got: {kty}")

    crv = cose_key.get(_COSE_KEY_CRV)
    if crv != _COSE_CRV_ED25519:
        raise ValueError(f"Expected Ed25519 curve (6), got: {crv}")

    x = cose_key.get(_COSE_KEY_X)
    if x is None:
        raise ValueError("COSE key missing 'x' parameter")

    x = bytes(x)
    if len(x) != 32:
        raise ValueError(f"Ed25519 public key must be 32 bytes, got {len(x)}")

    return x
