"""EnrolmentStore: file-backed storage for FIDO2 enrolment requests."""
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal


_DEFAULT_TTL = int(os.environ.get("ENROLMENT_TTL_SECONDS", str(48 * 3600)))
_DEFAULT_DIR = Path(os.environ.get("ENROLMENT_DIR", "/tmp/decpki-enrolments"))


@dataclass
class ValidatorSig:
    validator_name: str
    signature_hex: str
    signed_at: int


@dataclass
class EnrolmentRequest:
    id: str
    did: str
    public_key_hex: str
    public_key_cose_b64: str
    credential_id: str
    request_type: Literal["new", "add_credential"]
    existing_did: str | None
    submitted_at: int
    expires_at: int
    status: Literal["pending", "promoted", "expired", "cancelled"]
    signatures: list[ValidatorSig]
    threshold: int
    metadata: dict

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "EnrolmentRequest":
        sigs = [ValidatorSig(**s) for s in d.get("signatures", [])]
        return cls(
            id=d["id"],
            did=d["did"],
            public_key_hex=d["public_key_hex"],
            public_key_cose_b64=d.get("public_key_cose_b64", ""),
            credential_id=d["credential_id"],
            request_type=d.get("request_type", "new"),
            existing_did=d.get("existing_did"),
            submitted_at=d["submitted_at"],
            expires_at=d["expires_at"],
            status=d["status"],
            signatures=sigs,
            threshold=d.get("threshold", 2),
            metadata=d.get("metadata", {}),
        )


class DuplicateCredentialError(Exception):
    pass


class EnrolmentStore:
    def __init__(self, enrolment_dir: Path | None = None, threshold: int = 2):
        self._dir = enrolment_dir or _DEFAULT_DIR
        self._threshold = threshold
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / "promoted").mkdir(exist_ok=True)

    def _path(self, request_id: str) -> Path:
        return self._dir / f"{request_id}.json"

    def _all_credential_ids(self) -> set[str]:
        ids = set()
        for p in self._dir.glob("*.json"):
            try:
                req = EnrolmentRequest.from_dict(json.loads(p.read_text()))
                ids.add(req.credential_id)
            except Exception:
                pass
        for p in (self._dir / "promoted").glob("*.json"):
            try:
                req = EnrolmentRequest.from_dict(json.loads(p.read_text()))
                ids.add(req.credential_id)
            except Exception:
                pass
        return ids

    def create(
        self,
        did: str,
        public_key_hex: str,
        credential_id: str,
        public_key_cose_b64: str = "",
        request_type: str = "new",
        existing_did: str | None = None,
        metadata: dict | None = None,
    ) -> EnrolmentRequest:
        if credential_id in self._all_credential_ids():
            raise DuplicateCredentialError(f"Credential ID already registered: {credential_id}")

        now = int(time.time())
        req = EnrolmentRequest(
            id=str(uuid.uuid4()),
            did=did,
            public_key_hex=public_key_hex,
            public_key_cose_b64=public_key_cose_b64,
            credential_id=credential_id,
            request_type=request_type,
            existing_did=existing_did,
            submitted_at=now,
            expires_at=now + _DEFAULT_TTL,
            status="pending",
            signatures=[],
            threshold=self._threshold,
            metadata=metadata or {},
        )
        self._path(req.id).write_text(json.dumps(req.to_dict(), indent=2))
        return req

    def get(self, request_id: str) -> EnrolmentRequest | None:
        p = self._path(request_id)
        if not p.exists():
            promoted = self._dir / "promoted" / f"{request_id}.json"
            if promoted.exists():
                return EnrolmentRequest.from_dict(json.loads(promoted.read_text()))
            return None
        return EnrolmentRequest.from_dict(json.loads(p.read_text()))

    def list_pending(self) -> list[EnrolmentRequest]:
        result = []
        for p in sorted(self._dir.glob("*.json")):
            try:
                req = EnrolmentRequest.from_dict(json.loads(p.read_text()))
                result.append(req)
            except Exception:
                pass
        return result

    def add_signature(self, request_id: str, validator_name: str, signature_hex: str) -> EnrolmentRequest:
        req = self.get(request_id)
        if req is None:
            raise KeyError(f"Request not found: {request_id}")
        req.signatures.append(ValidatorSig(
            validator_name=validator_name,
            signature_hex=signature_hex,
            signed_at=int(time.time()),
        ))
        self._path(req.id).write_text(json.dumps(req.to_dict(), indent=2))
        return req

    def promote(self, request_id: str) -> EnrolmentRequest:
        req = self.get(request_id)
        if req is None:
            raise KeyError(f"Request not found: {request_id}")
        req.status = "promoted"
        promoted_path = self._dir / "promoted" / f"{request_id}.json"
        promoted_path.write_text(json.dumps(req.to_dict(), indent=2))
        self._path(request_id).unlink(missing_ok=True)
        return req
