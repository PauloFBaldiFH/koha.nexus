import sys
from pathlib import Path

CLIENT = Path(__file__).resolve().parents[1]
REPO = CLIENT.parents[1]
# As the embeddable Python's ._pth does on Windows: the client folder and
# the folder holding nexus_core.
for p in (str(CLIENT), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)
