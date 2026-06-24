import pytest
import click

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "cli"))
from decpki_cli import _parse_grace


def test_parse_grace_hours():
    assert _parse_grace("24h") == 86400


def test_parse_grace_days():
    assert _parse_grace("7d") == 604800


def test_parse_grace_seconds():
    assert _parse_grace("3600s") == 3600


def test_parse_grace_invalid():
    with pytest.raises(click.BadParameter):
        _parse_grace("1week")
