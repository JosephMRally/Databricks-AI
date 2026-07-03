"""Shared pytest fixtures / path setup for the dormant-email ELT tests."""

import os
import sys

import pytest

# Make the repo root (and thus the scripts/ package) importable from tests/.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FIXTURES = os.path.join(ROOT, "tests", "fixtures")


@pytest.fixture
def sample_pages_dir():
    """Directory holding synthetic real-format search_threads pages."""
    return os.path.join(FIXTURES, "sample_pages")
