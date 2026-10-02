"""Running a proposal, only after the person pressed Confirm.

  panel_action  the menu entry runs exactly as from its card (app.run_entry):
                config.sh --run <action>, or its background verb behind the
                loader. Koha's own routines, no SQL of ours.
  sql           a thread job behind the Pac-Man loader:
                  1. the safety backup (--backup-now) when the installer has it;
                  2. koha-mysql <instance> with
                       START TRANSACTION; <statement> LIMIT <previewed rows>; COMMIT;
                     so it can never touch more rows than the preview showed.
"""

from __future__ import annotations

import subprocess

from .. import menus
from ..tasks import TaskFailed
from .tools import Proposal, proposable_entries

BACKUP_VERB = ("--backup-now",)


def entry_for(p: Proposal) -> menus.Entry:
    entry = proposable_entries().get(p.action)
    if not entry:
        raise TaskFailed(f"{p.action} can no longer be run from the assistant")
    return entry


def sql_script(p: Proposal) -> str:
    return f"START TRANSACTION;\n{p.run_sql};\nSELECT ROW_COUNT();\nCOMMIT;\n"


def run_sql(instance: str, p: Proposal) -> int:
    """BLOCKS. Rows changed, as MariaDB counted them."""
    try:
        proc = subprocess.run(["koha-mysql", instance, "--batch", "--skip-column-names"],
                              input=sql_script(p), capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise TaskFailed(f"koha-mysql: {e}") from None
    if proc.returncode != 0:
        raise TaskFailed((proc.stderr.strip().splitlines() or ["koha-mysql failed"])[0], proc.returncode)
    lines = [ln for ln in proc.stdout.split() if ln.lstrip("-").isdigit()]
    return int(lines[-1]) if lines else 0
