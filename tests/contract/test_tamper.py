from decpki import (
    generate_bundle,
    register_identity,
    verify,
    IdentityLog,
    IdentityRecord,
    ValidatorNode,
    Outcome,
)


def test_tampered_bundle_detected(three_validators, tmp_path):
    v_alpha, v_beta, _ = three_validators
    log = IdentityLog.empty()
    record = IdentityRecord(
        did="did:local:tamper-test",
        public_key=ValidatorNode.generate("did:local:x").public_key,
        issued_at=0,
        issued_by=[],
    )
    register_identity(log, record, [v_alpha, v_beta], threshold=2)
    raw = generate_bundle(log, [v_alpha, v_beta], threshold=2, grace_seconds=3600)

    tampered = bytearray(raw)
    tampered[100] ^= 0xFF
    bundle_path = tmp_path / "tampered.cbor"
    bundle_path.write_bytes(bytes(tampered))

    result = verify(bundle_path, "did:local:tamper-test")
    assert result.outcome in (Outcome.TAMPERED, Outcome.INVALID), result.message
