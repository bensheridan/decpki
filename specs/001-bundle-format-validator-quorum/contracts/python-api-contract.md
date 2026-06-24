# Python API Contract: `decpki` Library

The `decpki` package exposes a public Python API for programmatic use. All public symbols
are importable from `decpki`.

---

## Verification API

### `verify(bundle_path: str | Path, did: str) -> VerifyResult`

Verify a DID against a trust bundle file. Pure local computation — no network calls.

**Parameters**:
- `bundle_path`: Path to a `.cbor` bundle file.
- `did`: The DID string to verify (e.g., `"did:local:payments-svc"`).

**Returns**: `VerifyResult` (see below)

**Raises**: `BundleDecodeError` if the file cannot be parsed as a valid CBOR bundle.

---

### `VerifyResult`

```python
@dataclass
class VerifyResult:
    outcome: Outcome          # enum — see below
    did: str                  # the queried DID
    bundle_expires_at: int    # Unix timestamp of bundle expiry
    record: IdentityRecord | None  # populated if outcome is VALID or INVALID
    message: str              # human-readable description
```

### `Outcome` (enum)

```python
class Outcome(str, Enum):
    VALID         = "valid"        # DID found, proof verified, bundle valid
    NOT_FOUND     = "not_found"    # DID not in bundle
    EXPIRED       = "expired"      # bundle expiry timestamp has passed
    TAMPERED      = "tampered"     # one or more validator signatures invalid
    INVALID       = "invalid"      # Merkle proof verification failed
    QUORUM_FAILURE = "quorum_failure"  # len(signatures) < threshold
```

---

## Bundle Generation API

### `generate_bundle(log: IdentityLog, validators: list[ValidatorNode], threshold: int, grace_seconds: int) -> bytes`

Generate a signed CBOR trust bundle.

**Parameters**:
- `log`: An `IdentityLog` containing the active identities to include.
- `validators`: List of `ValidatorNode` objects. Signatures are collected from each.
- `threshold`: Minimum number of signatures required. Raises `QuorumError` if
  `len(validators) < threshold`.
- `grace_seconds`: Number of seconds until the bundle expires.

**Returns**: Raw CBOR bytes of the signed bundle.

**Raises**:
- `QuorumError`: Fewer validators provided than `threshold`.

---

## Identity Registration API

### `register_identity(log: IdentityLog, record: IdentityRecord, validators: list[ValidatorNode], threshold: int) -> IdentityRecord`

Register a new identity in the log. Signs the record with the provided validators.

**Parameters**:
- `log`: The `IdentityLog` to write the new record to.
- `record`: A partially-constructed `IdentityRecord` (without `issued_at` or `issued_by` —
  those are filled by this function).
- `validators`: List of `ValidatorNode` objects that will co-sign the issuance.
- `threshold`: Minimum signatures required. Raises `QuorumError` if insufficient.

**Returns**: The completed `IdentityRecord` as written to the log.

**Raises**:
- `DuplicateDIDError`: DID already exists in the log.
- `QuorumError`: Fewer validators provided than `threshold`.

---

## Data Classes

### `IdentityRecord`

```python
@dataclass
class IdentityRecord:
    did: str
    public_key: bytes          # 32 bytes, ed25519
    issued_at: int             # logical block number
    issued_by: list[str]       # validator DIDs
    valid_until: int | None    # block number or None
    revoked_at: int | None     # block number or None
    metadata: dict[str, Any]
```

### `ValidatorNode`

```python
@dataclass
class ValidatorNode:
    did: str
    public_key: bytes          # 32 bytes, ed25519
    # private key held internally; not exposed via public API

    @classmethod
    def from_key_file(cls, path: str | Path) -> "ValidatorNode": ...

    def sign(self, data: bytes) -> bytes:
        """Sign arbitrary bytes. Returns 64-byte ed25519 signature."""
        ...
```

### `IdentityLog`

```python
class IdentityLog:
    @classmethod
    def load(cls, path: str | Path) -> "IdentityLog": ...

    @classmethod
    def empty(cls) -> "IdentityLog": ...

    def save(self, path: str | Path) -> None: ...

    def add(self, record: IdentityRecord) -> None:
        """Add a record. Raises DuplicateDIDError if DID already exists."""
        ...

    def get(self, did: str) -> IdentityRecord | None: ...

    def active_records(self) -> list[IdentityRecord]:
        """Returns all non-revoked records."""
        ...
```

---

## Exceptions

```python
class DecPKIError(Exception): ...

class QuorumError(DecPKIError): ...
    # .required: int
    # .provided: int

class DuplicateDIDError(DecPKIError): ...
    # .did: str

class BundleDecodeError(DecPKIError): ...
    # .reason: str
```
