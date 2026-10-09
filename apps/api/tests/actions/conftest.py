"""Isolated contract fixtures, not the F0 application or a production database."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from support import MemoryStore, fixture_context


@pytest.fixture
def store():
    return MemoryStore(fixture_context())
