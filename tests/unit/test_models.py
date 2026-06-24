import pytest

from decpki import IdentityLog, IdentityRecord, ValidatorNode, DuplicateDIDError


def _make_record(did="did:local:test"):
    return IdentityRecord(
        did=did,
        public_key=b"\x00" * 32,
        issued_at=1000,
        issued_by=["did:local:validator-alpha"],
    )


def test_add_raises_duplicate_did():
    log = IdentityLog.empty()
    log.add(_make_record())
    with pytest.raises(DuplicateDIDError) as exc:
        log.add(_make_record())
    assert exc.value.did == "did:local:test"


def test_active_records_excludes_revoked():
    log = IdentityLog.empty()
    r1 = _make_record("did:local:active")
    r2 = _make_record("did:local:revoked")
    r2.revoked_at = 1001
    log.add(r1)
    log.add(r2)
    active = log.active_records()
    assert len(active) == 1
    assert active[0].did == "did:local:active"


def test_validator_node_roundtrip(tmp_path):
    node = ValidatorNode.generate("did:local:validator-test")
    key_path = tmp_path / "test.key.json"
    node.save_key_file(key_path)
    loaded = ValidatorNode.from_key_file(key_path)
    assert loaded.did == node.did
    assert loaded.public_key == node.public_key
    msg = b"test message"
    sig = node.sign(msg)
    assert loaded.verify(sig, msg)


def test_log_save_and_load(tmp_path):
    log = IdentityLog.empty()
    log.add(_make_record("did:local:svc-a"))
    path = tmp_path / "log.json"
    log.save(path)
    loaded = IdentityLog.load(path)
    assert loaded.get("did:local:svc-a") is not None
