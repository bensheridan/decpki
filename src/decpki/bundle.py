import time
from typing import Any

import cbor2

from .exceptions import BundleDecodeError, QuorumError
from .merkle import build_tree, get_proof, get_root
from .models import (
    IdentityEntry,
    IdentityLog,
    IdentityRecord,
    MerkleProof,
    TrustBundle,
    ValidatorNode,
    ValidatorSignature,
)

CURRENT_FORMAT_VERSION = 1


def serialise_record(record: IdentityRecord) -> bytes:
    m = {
        "did": record.did,
        "issued_at": record.issued_at,
        "issued_by": record.issued_by,
        "meta": record.metadata,
        "pubkey": record.public_key,
        "revoked_at": record.revoked_at,
        "valid_until": record.valid_until,
    }
    return cbor2.dumps(m, canonical=True)


def _proof_to_cbor(proof: MerkleProof) -> dict:
    return {
        "leaf": proof.leaf_hash,
        "root": proof.root,
        "siblings": [{"h": s["h"], "s": s["s"]} for s in proof.siblings],
    }


def _proof_from_cbor(d: dict) -> MerkleProof:
    return MerkleProof(
        leaf_hash=bytes(d["leaf"]),
        siblings=[{"h": bytes(s["h"]), "s": s["s"]} for s in d["siblings"]],
        root=bytes(d["root"]),
    )


def _record_from_cbor(d: dict) -> IdentityRecord:
    return IdentityRecord(
        did=d["did"],
        public_key=bytes(d["pubkey"]),
        issued_at=d["issued_at"],
        issued_by=list(d["issued_by"]),
        valid_until=d.get("valid_until"),
        revoked_at=d.get("revoked_at"),
        metadata=dict(d.get("meta", {})),
    )


def serialise_bundle_for_signing(bundle: TrustBundle) -> bytes:
    identities = []
    for entry in bundle.identities:
        identities.append(
            {
                "did": entry.record.did,
                "issued_at": entry.record.issued_at,
                "issued_by": entry.record.issued_by,
                "meta": entry.record.metadata,
                "proof": _proof_to_cbor(entry.proof),
                "pubkey": entry.record.public_key,
                "revoked_at": entry.record.revoked_at,
                "valid_until": entry.record.valid_until,
            }
        )
    m: dict[str, Any] = {
        "expires_at": bundle.expires_at,
        "fmt_ver": bundle.format_version,
        "identities": identities,
        "issued_at": bundle.issued_at,
        "signatures": [],
        "snap_block": bundle.snapshot_block,
        "snap_root": bundle.snapshot_root,
        "threshold": bundle.threshold,
        "val_set": bundle.validator_set,
    }
    return cbor2.dumps(m, canonical=True)


def deserialise_bundle(raw: bytes) -> TrustBundle:
    try:
        m = cbor2.loads(raw)
    except Exception as e:
        raise BundleDecodeError(f"CBOR parse failed: {e}") from e

    if m.get("fmt_ver") != CURRENT_FORMAT_VERSION:
        raise BundleDecodeError(
            f"Unknown format version: {m.get('fmt_ver')} (expected {CURRENT_FORMAT_VERSION})"
        )

    try:
        identities = []
        for entry in m.get("identities", []):
            record = _record_from_cbor(entry)
            proof = _proof_from_cbor(entry["proof"])
            identities.append(IdentityEntry(record=record, proof=proof))

        signatures = []
        for sig in m.get("signatures", []):
            signatures.append(
                ValidatorSignature(
                    validator_did=sig["val_did"],
                    validator_pubkey=bytes(sig["val_pk"]),
                    signature=bytes(sig["sig"]),
                )
            )

        return TrustBundle(
            format_version=m["fmt_ver"],
            snapshot_block=m["snap_block"],
            snapshot_root=bytes(m["snap_root"]),
            issued_at=m["issued_at"],
            expires_at=m["expires_at"],
            threshold=m["threshold"],
            validator_set=list(m["val_set"]),
            identities=identities,
            signatures=signatures,
        )
    except (KeyError, TypeError) as e:
        raise BundleDecodeError(f"Malformed bundle structure: {e}") from e


def generate_bundle(
    log: IdentityLog,
    validators: list[ValidatorNode],
    threshold: int,
    grace_seconds: int,
) -> bytes:
    if len(validators) < threshold:
        raise QuorumError(required=threshold, provided=len(validators))

    active = sorted(log.active_records(), key=lambda r: r.did)
    leaf_data = [serialise_record(r) for r in active]
    tree = build_tree(leaf_data)
    root = get_root(tree)

    now = int(time.time())
    block = log.next_block

    identities = []
    for i, record in enumerate(active):
        proof_steps = get_proof(tree, i)
        from .merkle import _leaf_hash
        proof = MerkleProof(
            leaf_hash=_leaf_hash(leaf_data[i]),
            siblings=proof_steps,
            root=root,
        )
        identities.append(IdentityEntry(record=record, proof=proof))

    bundle = TrustBundle(
        format_version=CURRENT_FORMAT_VERSION,
        snapshot_block=block,
        snapshot_root=root,
        issued_at=now,
        expires_at=now + grace_seconds,
        threshold=threshold,
        validator_set=[v.did for v in validators],
        identities=identities,
        signatures=[],
    )

    signing_bytes = serialise_bundle_for_signing(bundle)

    sigs = []
    for validator in validators:
        sig = validator.sign(signing_bytes)
        sigs.append(
            ValidatorSignature(
                validator_did=validator.did,
                validator_pubkey=validator.public_key,
                signature=sig,
            )
        )
    bundle.signatures = sigs

    # Re-serialise with signatures included
    identities_cbor = []
    for entry in bundle.identities:
        identities_cbor.append(
            {
                "did": entry.record.did,
                "issued_at": entry.record.issued_at,
                "issued_by": entry.record.issued_by,
                "meta": entry.record.metadata,
                "proof": _proof_to_cbor(entry.proof),
                "pubkey": entry.record.public_key,
                "revoked_at": entry.record.revoked_at,
                "valid_until": entry.record.valid_until,
            }
        )
    sigs_cbor = [
        {"sig": s.signature, "val_did": s.validator_did, "val_pk": s.validator_pubkey}
        for s in sigs
    ]
    final = {
        "expires_at": bundle.expires_at,
        "fmt_ver": bundle.format_version,
        "identities": identities_cbor,
        "issued_at": bundle.issued_at,
        "signatures": sigs_cbor,
        "snap_block": bundle.snapshot_block,
        "snap_root": bundle.snapshot_root,
        "threshold": bundle.threshold,
        "val_set": bundle.validator_set,
    }
    return cbor2.dumps(final, canonical=True)
