"""Routines ported to the panel: their questions are Textual screens, their
work runs as `config.sh --task` behind the Pac-Man loader, their answers
come back as a result screen. No whiptail box is opened.

Each routine is an async function (app) run in a worker, so a flow reads
top to bottom with `await app.push_screen_wait(...)`. ROUTINES maps the
menu's --run action to it; menus.Entry(kind="native") marks the entries.
An installer without `--task` (older than the panel) keeps the classic
routine (app.run_entry falls back to it).
"""

from __future__ import annotations

from typing import Awaitable, Callable

from . import backup, database, diagnostics, install

Routine = Callable[[object], Awaitable[None]]

ROUTINES: dict[str, Routine] = {
    "backup-manual": backup.manual_backup,
    "backup-test": backup.test_backup,
    "backup-cloud": backup.cloud_backup,
    "restore": backup.restore,
    "db-maintenance": database.deep_maintenance,
    "reports": database.reports_pack,
    "install": install.install_koha,
    "credentials": install.credentials,
    "status": diagnostics.status,
    "health": diagnostics.health,
    "validation-report": diagnostics.validation_report,
    "apache-log": diagnostics.apache_log,
    "repair-services": diagnostics.repair_services,
}


def has(action: str) -> bool:
    return action in ROUTINES
