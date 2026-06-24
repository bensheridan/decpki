import json
import os
import pytest
from pathlib import Path

from decpki.models import IdentityLog, ValidatorNode


@pytest.fixture
def tmp_identity_log(tmp_path):
    log_path = tmp_path / "identity_log.json"
    log = IdentityLog.empty()
    log.save(log_path)
    return log, log_path


@pytest.fixture
def three_validators(tmp_path):
    nodes = []
    for name in ("alpha", "beta", "gamma"):
        key_path = tmp_path / f"{name}.key.json"
        node = ValidatorNode.generate(f"did:local:validator-{name}")
        node.save_key_file(key_path)
        nodes.append(node)
    return nodes
