"""What the status window shows, as plain JSON for ui/app.js.

The same sections as KohaEasy.Window.ps1: a banner (ok, starting, fault,
stopped), when it was checked and the latest backup, quick access, the
components. Texts are translated here, so app.js only places them.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict

from nexus_core import health
from nexus_core.state import ON_STATES, RUNNING, KohaStatus, Translate
from nexus_core.alerts import format_size

from . import config


def _local(epoch: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(epoch))


def build(status: KohaStatus, debian_running: bool, t: Translate = str,
          fmt: Callable[[float], str] = _local) -> Dict[str, Any]:
    linux = status.linux
    rows = health.component_rows(debian_running, linux)
    summary = health.summarize(rows, status.state, t)
    backup = t("Latest backup: none yet")
    if linux is not None and linux.backup.last_epoch > 0:
        b = linux.backup
        backup = t("Latest backup: {0} ({1})").format(fmt(b.last_epoch), format_size(b.last_size))
    on = status.state in ON_STATES
    return {
        "state": status.state,
        "banner": {"level": summary.level, "text": summary.text, "broken": summary.broken},
        "checked": t("Checked at {0}").format(fmt(status.checked_at)) if status.checked_at > 0 else "",
        "backup": backup,
        "links": [
            {"key": "staff", "text": t("Staff interface"), "url": config.STAFF_URL,
             "enabled": status.state == RUNNING},
            {"key": "opac", "text": t("Public catalog (OPAC)"), "url": config.OPAC_URL,
             "enabled": status.state == RUNNING},
        ],
        "components": [
            {"unit": r.unit, "name": health.row_name(r, t), "state": r.state,
             "text": health.row_state_text(r, t), "broken": r.unit in summary.broken}
            for r in rows
        ],
        "actions": [
            {"key": "start", "text": t("Start Koha"), "enabled": not on and status.state != "not_installed"},
            {"key": "panel", "text": t("Management panel"), "enabled": True},
            {"key": "restart", "text": t("Restart Koha"), "enabled": on},
            {"key": "terminal", "text": t("Open the Debian terminal"), "enabled": debian_running},
            {"key": "poweroff", "text": t("Shut down the PC safely"), "enabled": True},
        ],
        "labels": {
            "quick": t("Quick access"),
            "components": t("Components"),
            "actions": t("Actions"),
        },
    }
