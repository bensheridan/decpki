import pytest

from decpki import (
    generate_bundle,
    register_identity,
    verify,
    IdentityLog,
    IdentityRecord,
    ValidatorNode,
    Outcome,
    QuorumError,
)
from decpki.bundle import deserialise_bundle, serialise_bundle_for_signing
from decpki.models import ValidatorSignature, TrustBundle


def _make_registered_log(validators, threshold=2):
    log = IdentityLog.empty()
    record = IdentityRecord(
        did="did:local:test-svc",
        public_key=ValidatorNode.generate("did:local:x").public_key,
        issued_at=0,
        issued_by=[],
    )
    register_identity(log, record, validators, threshold)
    return log


def test_generate_bundle_raises_quorum_error_on_insufficient_validators(three_validators):
    v_alpha = three_validators[0]
    log = _make_registered_log([v_alpha, three_validators[1]], threshold=2)
    with pytest.raises(QuorumError):
        generate_bundle(log, [v_alpha], threshold=2, grace_seconds=3600)


def test_one_sig_bundle_rejected_by_client(three_validators, tmp_path):
    v_alpha, v_beta, _ = three_validators
    log = _make_registered_log([v_alpha, v_beta], threshold=2)
    # Generate with 2 sigs so bundle gen works, then mutate to strip one signature
    raw = generate_bundle(log, [v_alpha, v_beta], threshold=2, grace_seconds=3600)
    bundle = deserialise_bundle(raw)

    # Build a 1-sig bundle manually
    one_sig_bundle = TrustBundle(
        format_version=bundle.format_version,
        snapshot_block=bundle.snapshot_block,
        snapshot_root=bundle.snapshot_root,
        issued_at=bundle.issued_at,
        expires_at=bundle.expires_at,
        threshold=2,
        validator_set=bundle.validator_set,
        identities=bundle.identities,
        signatures=bundle.signatures[:1],
    )
    import cbor2
    sigs_cbor = [
        {"sig": s.signature, "val_did": s.validator_did, "val_pk": s.validator_pubkey}
        for s in one_sig_bundle.signatures
    ]
    identities_cbor = []
    from decpki.bundle import _proof_to_cbor
    for e in one_sig_bundle.identities:
        identities_cbor.append({
            "did": e.record.did,
            "issued_at": e.record.issued_at,
            "issued_by": e.record.issued_by,
            "meta": e.record.metadata,
            "proof": _proof_to_cbor(e.proof),
            "pubkey": e.record.public_key,
            "revoked_at": e.record.revoked_at,
            "valid_until": e.record.valid_until,
        })
    raw_1sig = cbor2.dumps({
        "expires_at": one_sig_bundle.expires_at,
        "fmt_ver": one_sig_bundle.format_version,
        "identities": identities_cbor,
        "issued_at": one_sig_bundle.issued_at,
        "signatures": sigs_cbor,
        "snap_block": one_sig_bundle.snapshot_block,
        "snap_root": one_sig_bundle.snapshot_root,
        "threshold": 2,
        "val_set": one_sig_bundle.validator_set,
    }, canonical=True)

    bundle_path = tmp_path / "1sig.cbor"
    bundle_path.write_bytes(raw_1sig)
    result = verify(bundle_path, "did:local:test-svc")
    assert result.outcome == Outcome.QUORUM_FAILURE


def test_two_sig_bundle_accepted(three_validators, tmp_path):
    v_alpha, v_beta, _ = three_validators
    log = _make_registered_log([v_alpha, v_beta], threshold=2)
    raw = generate_bundle(log, [v_alpha, v_beta], threshold=2, grace_seconds=3600)
    bundle_path = tmp_path / "2sig.cbor"
    bundle_path.write_bytes(raw)
    result = verify(bundle_path, "did:local:test-svc")
    assert result.outcome == Outcome.VALID
