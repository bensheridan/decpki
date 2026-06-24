import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .exceptions import DuplicateDIDError


@dataclass
class IdentityRecord:
    did: str
    public_key: bytes
    issued_at: int
    issued_by: list[str]
    valid_until: int | None = None
    revoked_at: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


@dataclass
class MerkleProof:
    leaf_hash: bytes
    siblings: list[dict]
    root: bytes


@dataclass
class ValidatorSignature:
    validator_did: str
    validator_pubkey: bytes
    signature: bytes


@dataclass
class IdentityEntry:
    record: IdentityRecord
    proof: MerkleProof


@dataclass
class TrustBundle:
    format_version: int
    snapshot_block: int
    snapshot_root: bytes
    issued_at: int
    expires_at: int
    threshold: int
    validator_set: list[str]
    identities: list[IdentityEntry]
    signatures: list[ValidatorSignature]


class ValidatorNode:
    def __init__(self, did: str, private_key: Ed25519PrivateKey):
        self.did = did
        self._private_key = private_key
        self.public_key: bytes = private_key.public_key().public_bytes_raw()

    @classmethod
    def generate(cls, did: str) -> "ValidatorNode":
        return cls(did, Ed25519PrivateKey.generate())

    @classmethod
    def from_key_file(cls, path: str | Path) -> "ValidatorNode":
        data = json.loads(Path(path).read_text())
        seed = bytes.fromhex(data["private_key_seed"])
        private_key = Ed25519PrivateKey.from_private_bytes(seed)
        return cls(data["did"], private_key)

    def save_key_file(self, path: str | Path) -> None:
        path = Path(path)
        seed = self._private_key.private_bytes_raw()
        data = {
            "did": self.did,
            "public_key": self.public_key.hex(),
            "private_key_seed": seed.hex(),
        }
        path.write_text(json.dumps(data, indent=2))
        os.chmod(path, 0o600)

    def sign(self, data: bytes) -> bytes:
        return self._private_key.sign(data)

    def verify(self, signature: bytes, data: bytes) -> bool:
        try:
            self._private_key.public_key().verify(signature, data)
            return True
        except Exception:
            return False


class IdentityLog:
    def __init__(self, records: list[IdentityRecord] | None = None):
        self._records: list[IdentityRecord] = records or []

    @classmethod
    def empty(cls) -> "IdentityLog":
        return cls([])

    @classmethod
    def load(cls, path: str | Path) -> "IdentityLog":
        data = json.loads(Path(path).read_text())
        records = []
        for r in data.get("records", []):
            records.append(
                IdentityRecord(
                    did=r["did"],
                    public_key=bytes.fromhex(r["public_key"]),
                    issued_at=r["issued_at"],
                    issued_by=r["issued_by"],
                    valid_until=r.get("valid_until"),
                    revoked_at=r.get("revoked_at"),
                    metadata=r.get("metadata", {}),
                )
            )
        return cls(records)

    def save(self, path: str | Path) -> None:
        records = []
        for r in self._records:
            records.append(
                {
                    "did": r.did,
                    "public_key": r.public_key.hex(),
                    "issued_at": r.issued_at,
                    "issued_by": r.issued_by,
                    "valid_until": r.valid_until,
                    "revoked_at": r.revoked_at,
                    "metadata": r.metadata,
                }
            )
        Path(path).write_text(json.dumps({"records": records}, indent=2))

    def add(self, record: IdentityRecord) -> None:
        if any(r.did == record.did for r in self._records):
            raise DuplicateDIDError(record.did)
        self._records.append(record)

    def get(self, did: str) -> IdentityRecord | None:
        for r in self._records:
            if r.did == did:
                return r
        return None

    def active_records(self) -> list[IdentityRecord]:
        return [r for r in self._records if r.is_active]

    @property
    def next_block(self) -> int:
        if not self._records:
            return 1000
        return max(r.issued_at for r in self._records) + 1
