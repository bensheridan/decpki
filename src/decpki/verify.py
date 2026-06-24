import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

from .bundle import deserialise_bundle, serialise_bundle_for_signing, serialise_record
from .exceptions import BundleDecodeError
from .merkle import verify_proof, _leaf_hash
from .models import TrustBundle


class Outcome(str, Enum):
    VALID = "valid"
    NOT_FOUND = "not_found"
    EXPIRED = "expired"
    TAMPERED = "tampered"
    INVALID = "invalid"
    QUORUM_FAILURE = "quorum_failure"


@dataclass
class VerifyResult:
    outcome: Outcome
    did: str
    bundle_expires_at: int
    record: object | None
    message: str


def verify(bundle_path: str | Path, did: str) -> VerifyResult:
    raw = Path(bundle_path).read_bytes()
    bundle = deserialise_bundle(raw)

    def result(outcome: Outcome, record=None, msg: str = "") -> VerifyResult:
        return VerifyResult(
            outcome=outcome,
            did=did,
            bundle_expires_at=bundle.expires_at,
            record=record,
            message=msg,
        )

    # 1. Quorum check
    if len(bundle.signatures) < bundle.threshold:
        return result(
            Outcome.QUORUM_FAILURE,
            msg=(
                f"QUORUM FAILURE: bundle has {len(bundle.signatures)} signature(s),"
                f" threshold is {bundle.threshold}"
            ),
        )

    # 2. Signature verification — reconstruct signing bytes (signatures=[])
    signing_bundle = TrustBundle(
        format_version=bundle.format_version,
        snapshot_block=bundle.snapshot_block,
        snapshot_root=bundle.snapshot_root,
        issued_at=bundle.issued_at,
        expires_at=bundle.expires_at,
        threshold=bundle.threshold,
        validator_set=bundle.validator_set,
        identities=bundle.identities,
        signatures=[],
    )
    signing_bytes = serialise_bundle_for_signing(signing_bundle)

    for sig in bundle.signatures:
        try:
            pub = Ed25519PublicKey.from_public_bytes(sig.validator_pubkey)
            pub.verify(sig.signature, signing_bytes)
        except (InvalidSignature, Exception):
            return result(
                Outcome.TAMPERED,
                msg=f"TAMPERED: signature verification failed for {sig.validator_did}",
            )

    # 3. Expiry check
    if bundle.expires_at <= time.time():
        import datetime
        expired_at = datetime.datetime.fromtimestamp(bundle.expires_at, tz=datetime.timezone.utc)
        return result(
            Outcome.EXPIRED,
            msg=f"EXPIRED: bundle expired at {expired_at.isoformat()}",
        )

    # 4. Merkle root recomputation
    from .bundle import serialise_record
    from .merkle import build_tree, get_root
    active_sorted = sorted(bundle.identities, key=lambda e: e.record.did)
    leaf_data = [serialise_record(e.record) for e in active_sorted]
    tree = build_tree(leaf_data)
    computed_root = get_root(tree)
    if computed_root != bundle.snapshot_root:
        return result(
            Outcome.INVALID,
            msg=f"INVALID: Merkle root mismatch — bundle may be corrupted",
        )

    # 5. DID lookup
    entry = next((e for e in bundle.identities if e.record.did == did), None)
    if entry is None:
        return result(
            Outcome.NOT_FOUND,
            msg=f"NOT FOUND: {did} is not in this bundle",
        )

    # 6. Inclusion proof
    leaf_bytes = serialise_record(entry.record)
    if not verify_proof(leaf_bytes, entry.proof.siblings, bundle.snapshot_root):
        return result(
            Outcome.INVALID,
            record=entry.record,
            msg=f"INVALID: Merkle proof verification failed for {did}",
        )

    return result(
        Outcome.VALID,
        record=entry.record,
        msg=f"VALID: {did} is a trusted identity",
    )
