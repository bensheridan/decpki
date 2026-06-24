import time

import pytest

from decpki import (
    generate_bundle,
    register_identity,
    verify,
    IdentityLog,
    IdentityRecord,
    ValidatorNode,
    Outcome,
)


def _setup_log_and_bundle(validators, grace_seconds, tmp_path):
    v_alpha, v_beta = validators[0], validators[1]
    log = IdentityLog.empty()
    record = IdentityRecord(
        did="did:local:expiry-test-svc",
        public_key=ValidatorNode.generate("did:local:x").public_key,
        issued_at=0,
        issued_by=[],
    )
    register_identity(log, record, [v_alpha, v_beta], threshold=2)
    raw = generate_bundle(log, [v_alpha, v_beta], threshold=2, grace_seconds=grace_seconds)
    bundle_path = tmp_path / "bundle.cbor"
    bundle_path.write_bytes(raw)
    return bundle_path


def test_expired_bundle_rejected(three_validators, tmp_path):
    bundle_path = _setup_log_and_bundle(three_validators, grace_seconds=1, tmp_path=tmp_path)
    time.sleep(2)
    result = verify(bundle_path, "did:local:expiry-test-svc")
    assert result.outcome == Outcome.EXPIRED


def test_fresh_bundle_accepted(three_validators, tmp_path):
    bundle_path = _setup_log_and_bundle(three_validators, grace_seconds=3600, tmp_path=tmp_path)
    result = verify(bundle_path, "did:local:expiry-test-svc")
    assert result.outcome == Outcome.VALID
