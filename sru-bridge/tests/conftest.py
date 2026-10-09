import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(ROOT))


@pytest.fixture
def raw_record() -> str:
    return (FIXTURES / "rawrecord_tabamex.txt").read_text().strip()


@pytest.fixture
def results_page() -> str:
    return (FIXTURES / "zeus_results.html").read_text()


@pytest.fixture
def marcxml_page() -> str:
    return (FIXTURES / "zeus_marcxml.html").read_text()
