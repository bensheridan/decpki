import pytest

from decpki import (
    generate_bundle,
    register_identity,
    IdentityLog,
    IdentityRecord,
    ValidatorNode,
    QuorumError,
)
from decpki.bundle import deserialise_bundle, serialise_record, serialise_bundle_for_signing


def _log_with_identity(validators):
    log = IdentityLog.empty()
    record = IdentityRecord(
        did="did:local:bundle-test",
        public_key=ValidatorNode.generate("did:local:x").public_key,
        issued_at=0,
        issued_by=[],
    )
    register_identity(log, record, validators, threshold=2)
    return log


def test_generate_bundle_quorum_error(three_validators):
    log = _log_with_identity(three_validators[:2])
    with pytest.raises(QuorumError) as exc:
        generate_bundle(log, [three_validators[0]], threshold=2, grace_seconds=3600)
    assert exc.value.required == 2
    assert exc.value.provided == 1


def test_bundle_roundtrip(three_validators):
    v_alpha, v_beta, _ = three_validators
    log = _log_with_identity([v_alpha, v_beta])
    raw = generate_bundle(log, [v_alpha, v_beta], threshold=2, grace_seconds=3600)
    bundle = deserialise_bundle(raw)
    assert bundle.format_version == 1
    assert len(bundle.identities) == 1
    assert bundle.identities[0].record.did == "did:local:bundle-test"
    assert len(bundle.signatures) == 2
    assert bundle.threshold == 2


def test_serialise_record_is_deterministic():
    node = ValidatorNode.generate("did:local:x")
    record = IdentityRecord(
        did="did:local:svc",
        public_key=node.public_key,
        issued_at=1000,
        issued_by=["did:local:v-alpha"],
        metadata={"env": "prod"},
    )
    b1 = serialise_record(record)
    b2 = serialise_record(record)
    assert b1 == b2
