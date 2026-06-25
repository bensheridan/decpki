"""COSE key extraction from WebAuthn attestation objects.

Supports ed25519 (COSE alg -8) and ES256 / P-256 (COSE alg -7).
All other algorithms raise ValueError.
"""
import base64
import struct

import cbor2


_COSE_ALG_EDDSA = -8
_COSE_ALG_ES256 = -7

_COSE_KTY_OKP = 1
_COSE_KTY_EC2 = 2

_COSE_CRV_ED25519 = 6
_COSE_CRV_P256 = 1

_COSE_KEY_KTY = 1
_COSE_KEY_ALG = 3
_COSE_KEY_CRV = -1
_COSE_KEY_X = -2
_COSE_KEY_Y = -3

_AUTHDATA_MIN_LEN = 37
_AUTHDATA_FLAG_AT = 0x40


def _b64url_decode(s: str) -> bytes:
    s = s.replace("-", "+").replace("_", "/")
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.b64decode(s)


def _parse_auth_data(attestation_object: bytes) -> bytes:
    """Decode CBOR attestation object and return authData bytes."""
    try:
        att = cbor2.loads(attestation_object)
    except Exception as e:
        raise ValueError(f"Failed to decode CBOR attestation object: {e}") from e

    if not isinstance(att, dict):
        raise ValueError(f"Expected CBOR map, got {type(att).__name__}")

    auth_data = att.get("authData")
    if auth_data is None:
        raise ValueError("attestationObject missing 'authData' field")

    auth_data = bytes(auth_data)
    if len(auth_data) < _AUTHDATA_MIN_LEN:
        raise ValueError(f"authData too short: {len(auth_data)} bytes")

    flags = auth_data[32]
    if not (flags & _AUTHDATA_FLAG_AT):
        raise ValueError("authData AT flag not set — no attested credential data present")

    return auth_data


def _extract_cose_key(auth_data: bytes) -> dict:
    """Parse COSE public key map from authData."""
    offset = 37
    if len(auth_data) < offset + 18:
        raise ValueError("authData truncated in attested credential data header")

    offset += 16  # skip aaguid
    cred_id_len = struct.unpack(">H", auth_data[offset:offset + 2])[0]
    offset += 2 + cred_id_len

    cose_key_bytes = auth_data[offset:]
    if not cose_key_bytes:
        raise ValueError("authData contains no COSE public key bytes")

    try:
        return cbor2.loads(cose_key_bytes)
    except Exception as e:
        raise ValueError(f"Failed to decode COSE key: {e}") from e


def extract_pubkey(attestation_object: bytes | str) -> tuple[str, str]:
    """Extract a public key from a WebAuthn attestation object.

    Returns:
        (public_key_hex, algorithm) where algorithm is "ed25519" or "es256".
        For ed25519: public_key_hex is the 32-byte raw key as hex.
        For es256: public_key_hex is the 65-byte uncompressed EC point (04||x||y) as hex.

    Raises:
        ValueError: If the algorithm is unsupported or the object is malformed.
    """
    if isinstance(attestation_object, str):
        attestation_object = _b64url_decode(attestation_object)

    auth_data = _parse_auth_data(attestation_object)
    cose_key = _extract_cose_key(auth_data)

    alg = cose_key.get(_COSE_KEY_ALG)

    if alg == _COSE_ALG_EDDSA:
        return _extract_ed25519(cose_key)
    elif alg == _COSE_ALG_ES256:
        return _extract_es256(cose_key)
    else:
        raise ValueError(
            f"Unsupported COSE algorithm: {alg}. Only ed25519 (alg -8) and ES256 (alg -7) are accepted."
        )


def _extract_ed25519(cose_key: dict) -> tuple[str, str]:
    kty = cose_key.get(_COSE_KEY_KTY)
    if kty != _COSE_KTY_OKP:
        raise ValueError(f"Expected OKP key type (1) for ed25519, got: {kty}")

    crv = cose_key.get(_COSE_KEY_CRV)
    if crv != _COSE_CRV_ED25519:
        raise ValueError(f"Expected Ed25519 curve (6), got: {crv}")

    x = cose_key.get(_COSE_KEY_X)
    if x is None:
        raise ValueError("COSE key missing 'x' parameter")

    x = bytes(x)
    if len(x) != 32:
        raise ValueError(f"Ed25519 public key must be 32 bytes, got {len(x)}")

    return x.hex(), "ed25519"


def _extract_es256(cose_key: dict) -> tuple[str, str]:
    kty = cose_key.get(_COSE_KEY_KTY)
    if kty != _COSE_KTY_EC2:
        raise ValueError(f"Expected EC2 key type (2) for ES256, got: {kty}")

    crv = cose_key.get(_COSE_KEY_CRV)
    if crv != _COSE_CRV_P256:
        raise ValueError(f"Expected P-256 curve (1), got: {crv}")

    x = bytes(cose_key.get(_COSE_KEY_X) or b"")
    y = bytes(cose_key.get(_COSE_KEY_Y) or b"")
    if len(x) != 32 or len(y) != 32:
        raise ValueError(f"ES256 x/y must each be 32 bytes, got x={len(x)}, y={len(y)}")

    uncompressed = b"\x04" + x + y
    return uncompressed.hex(), "es256"


# Backwards-compatible alias used by existing tests
def extract_ed25519_pubkey(attestation_object: bytes | str) -> bytes:
    hex_key, alg = extract_pubkey(attestation_object)
    if alg != "ed25519":
        raise ValueError(f"Expected ed25519, got {alg}")
    return bytes.fromhex(hex_key)
