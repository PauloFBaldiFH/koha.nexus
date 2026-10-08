import sys
from pathlib import Path

PANEL = Path(__file__).resolve().parents[1]
REPO = PANEL.parent
sys.path.insert(0, str(PANEL))
INSTALLER = REPO / "installer"

import pytest


@pytest.fixture(autouse=True)
def _theme_file_of_the_test(tmp_path, monkeypatch):
    # The panel keeps the chosen theme in /etc/koha-easy-install: the tests
    # never touch the one of the machine they run on.
    monkeypatch.setenv("KEI_PANEL_THEME_FILE", str(tmp_path / "panel-theme.conf"))
