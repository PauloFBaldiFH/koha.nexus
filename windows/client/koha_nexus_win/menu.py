"""The tray menu as data, from KohaEasy.Tray.ps1 (Add-Item calls, Update-Menu).

tray.py turns these entries into pystray items; keeping them here, pure,
lets the order, the texts and the enabled rules be tested on Linux.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Mapping, Optional

from nexus_core.state import NOT_INSTALLED, ON_STATES, RUNNING, Translate, state_text


@dataclass(frozen=True)
class Entry:
    key: str                  # action key ("" for the header, "-" for a separator)
    text: str = ""
    enabled: bool = True
    checked: Optional[bool] = None   # None: not a check item
    default: bool = False            # the double-click action
    confirm: str = ""                # a question to ask first


SEPARATOR = Entry("-")


def entries(state: str, saved: Mapping[str, Any], t: Translate = str) -> List[Entry]:
    on = state in ON_STATES
    running = state == RUNNING
    return [
        Entry("", state_text(state, t), enabled=False),
        SEPARATOR,
        Entry("window", t("Service status"), default=True),
        Entry("staff", t("Open the staff interface"), enabled=running),
        Entry("opac", t("Open the public catalog"), enabled=running),
        SEPARATOR,
        Entry("start", t("Start Koha"), enabled=not on and state != NOT_INSTALLED),
        Entry("stop", t("Stop Koha"), enabled=on),
        Entry("restart", t("Restart Koha services"), enabled=on),
        Entry("reindex", t("Rebuild search index"), enabled=on,
              confirm=t("Rebuild the search index from scratch?") + "\n\n" + t(
                  "Searches in the catalog may be incomplete until it finishes. "
                  "On large catalogs this takes several minutes.")),
        SEPARATOR,
        Entry("poweroff", t("Shut down the PC safely")),
        SEPARATOR,
        Entry("report", t("Export diagnostics (.txt)")),
        Entry("diagnostics", t("Export diagnostics (.zip)")),
        Entry("disk", t("Check disk space")),
        Entry("backups", t("Open the backups folder")),
        Entry("panel", t("Open the control panel")),
        SEPARATOR,
        Entry("autostart", t("Start Koha when I sign in to Windows"), checked=saved.get("autostart") == "logon"),
        Entry("notify_backup", t("Notify me when the nightly backup succeeds"),
              checked=bool(saved.get("notifyBackupOk"))),
        SEPARATOR,
        Entry("close", t("Close this icon"),
              confirm=t("Close the Koha icon? Koha can keep running in the background, so the catalog "
                        "and the nightly backup keep working.")),
    ]


# Menu key -> KohaEasy.ps1 verb (and arguments), for the keys that are verbs.
VERB_OF = {
    "start": ("Start",),
    "stop": ("Stop",),
    "restart": ("RestartServices",),
    "reindex": ("RebuildIndex",),
    "poweroff": ("SafeShutdown",),
    "report": ("ExportReport",),
    "diagnostics": ("ExportDiagnostics",),
    "disk": ("CheckDisk",),
    "panel": ("Panel",),
}

# Seconds until the next status check after an action (Request-Check).
RECHECK_AFTER = {"start": 5, "stop": 5, "restart": 20, "poweroff": 5, "panel": 5}
