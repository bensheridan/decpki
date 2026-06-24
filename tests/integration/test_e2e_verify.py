from decpki import (
    generate_bundle,
    register_identity,
    verify,
    IdentityLog,
    IdentityRecord,
    ValidatorNode,
    Outcome,
)


def test_full_offline_verification(three_validators, tmp_path):
    v_alpha, v_beta, v_gamma = three_validators
    log = IdentityLog.empty()
    log_path = tmp_path / "log.json"

    record = IdentityRecord(
        did="did:local:payments-svc",
        public_key=ValidatorNode.generate("did:local:tmp").public_key,
        issued_at=0,
        issued_by=[],
        metadata={"env": "prod"},
    )
    register_identity(log, record, [v_alpha, v_beta], threshold=2)
    log.save(log_path)

    raw = generate_bundle(log, [v_alpha, v_beta], threshold=2, grace_seconds=3600)
    bundle_path = tmp_path / "bundle.cbor"
    bundle_path.write_bytes(raw)

    result = verify(bundle_path, "did:local:payments-svc")
    assert result.outcome == Outcome.VALID, result.message

    result2 = verify(bundle_path, "did:local:nonexistent")
    assert result2.outcome == Outcome.NOT_FOUND


def test_three_identities_bundle(three_validators, tmp_path):
    v_alpha, v_beta, v_gamma = three_validators
    log = IdentityLog.empty()

    for name in ("svc-a", "svc-b", "svc-c"):
        r = IdentityRecord(
            did=f"did:local:{name}",
            public_key=ValidatorNode.generate("did:local:tmp").public_key,
            issued_at=0,
            issued_by=[],
        )
        register_identity(log, r, [v_alpha, v_beta], threshold=2)

    raw = generate_bundle(log, [v_alpha, v_beta, v_gamma], threshold=2, grace_seconds=3600)
    bundle_path = tmp_path / "bundle.cbor"
    bundle_path.write_bytes(raw)

    for name in ("svc-a", "svc-b", "svc-c"):
        result = verify(bundle_path, f"did:local:{name}")
        assert result.outcome == Outcome.VALID, f"{name}: {result.message}"
