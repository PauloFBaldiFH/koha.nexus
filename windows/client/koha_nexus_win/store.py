"""state.json, shared with the PowerShell tools (Get-KohaState / Set-KohaState).

Both sides read the whole file, merge, and write it back through a
temporary file that replaces the old one, so a shortcut and the tray writing
at the same time never leave half a file. Keys this side does not know are
kept as they are.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Mapping

# $script:StateDefaults of KohaEasy.Core.psm1 (the keys this client reads).
DEFAULTS: Dict[str, Any] = {
    "desired": "running",
    "autostart": "logon",
    "startedAt": 0,
    "lastState": "",
    "firstSeen": 0,
    "lastBackupLogEpoch": 0,
    "lastStaleBackupWarn": 0,
    "lastDiskLevel": "ok",
    "lastDiskWarn": 0,
    "lastRecoveryEpoch": 0,
    "lastRecoveryNotice": 0,
    "notifyBackupOk": True,
    "appIdShortcut": False,
    "trayClosed": False,
}


class JsonStateStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> Dict[str, Any]:
        state = dict(DEFAULTS)
        try:
            # utf-8-sig: a file saved with a BOM by another tool still reads.
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                state.update(data)
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            # Get-KohaState keeps a damaged file aside; this side only reads
            # defaults and leaves the file to the PowerShell tools.
            pass
        if state.get("desired") not in ("running", "stopped"):
            state["desired"] = "running"
        if state.get("autostart") not in ("logon", "manual"):
            state["autostart"] = "logon"
        return state

    def save(self, changes: Mapping[str, Any]) -> None:
        state = self.load()
        state.update(changes)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)
