import sys
from pathlib import Path

PANEL = Path(__file__).resolve().parents[1]
REPO = PANEL.parent
sys.path.insert(0, str(PANEL))
INSTALLER = REPO / "installer"
