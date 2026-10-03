"""Simulated `--task` answers for demo mode and the tests: the same @@
lines the installer prints, fed through the real parser."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .bridge import TaskOutcome
    from .tasks import Reporter

_HOME = "/root"
_NEWEST = "/var/backups/koha_sql/koha_library_2026-10-02_03h00.sql.gz"

_SCRIPTS: dict[str, list[str]] = {
    "info": [
        "@@result real_user=root", f"@@result real_home={_HOME}", "@@result server_ip=192.0.2.10",
        "@@result dir_sql=/var/backups/koha_sql", "@@result koha_installed=yes",
        f"@@result newest={_NEWEST}", "@@result newest_date=2026-10-02 03:00",
        "@@result newest_size=46M", "@@result rclone=yes", "@@result rclone_remote=gdrive",
    ],
    "backup-manual": [
        "@@note Generating the backup...",
        "@@result file={0}/koha_library_manual_2026-10-03_12h00.sql.gz", "@@result size=46M",
        "@@result scp=scp root@192.0.2.10:{0}/koha_library_manual_2026-10-03_12h00.sql.gz Downloads/",
        "@@result user=root",
    ],
    "backup-test": [
        "@@ask Test Backup\tRun the test now?", "@@note Importing into a temporary database...",
        f"@@result file={_NEWEST}", "@@result tables=312", "@@result biblios=48210",
        "@@result patrons=3921", "@@msg ok OK\tBACKUP IS INTACT AND RESTORABLE.",
    ],
    "restore-check": [
        "@@note Checking the backup file...", "@@result size_mb=180", "@@result need_mb=526",
        "@@result free_mb=41000", "@@result has_sql=yes", "@@result complete=yes",
    ],
    "restore": [
        "@@title Restoring the catalog",
        "@@step Testing the backup in a temporary database", "@@done 0 Testing the backup in a temporary database",
        "@@step Saving a safety backup", "@@done 0 Saving a safety backup",
        "@@note Safety backup: /var/backups/koha_sql/PRE-RESTORE_2026-10-03_12h00.sql.gz",
        "@@step Stopping Koha services", "@@done 0 Stopping Koha services",
        "@@step Recreating the database", "@@done 0 Recreating the database",
        "@@step Importing the catalog", "@@done 0 Importing the catalog",
        "@@step Upgrading the database schema", "@@done 0 Upgrading the database schema",
        "@@step Synchronizing the search engine", "@@done 0 Synchronizing the search engine",
        "@@step Reindexing the catalog", "@@done 0 Reindexing the catalog",
        "@@step Restarting Koha services", "@@done 0 Restarting Koha services",
        "@@step Checking that everything works", "@@done 0 Checking that everything works",
        "@@result engine=Zebra", "@@result tables=312",
        "@@result safety_backup=/var/backups/koha_sql/PRE-RESTORE_2026-10-03_12h00.sql.gz",
        "@@msg ok OK\tCatalog restored and indexed successfully!",
    ],
    "cloud-prepare": ["@@step Installing rclone", "@@done 0 Installing rclone"],
    "cloud-token": [
        "@@step Registering 'gdrive' remote in Rclone...", "@@done 0 Registering 'gdrive' remote in Rclone...",
        "@@note Testing the real cloud upload...",
        "@@msg ok OK\tCloud enabled and tested successfully.",
    ],
    "cloud-authorize": [
        "@@result auth_url=http://127.0.0.1:53682/auth?state=demo",
        "@@result auth_tunnel=ssh -L 53682:127.0.0.1:53682 root@192.0.2.10",
        "@@note Waiting for the authorization...",
        "@@step Registering 'gdrive' remote in Rclone...", "@@done 0 Registering 'gdrive' remote in Rclone...",
        "@@msg ok OK\tCloud enabled and tested successfully.",
    ],
    "cloud-remotes": ["@@result remote=gdrive", "@@result remote=onedrive"],
    "db-maintenance": [
        "@@ask Deep Maintenance\tThis routine will:\\n\\n• Repair and optimize MariaDB tables\\n\\nContinue?",
        "@@title Deep maintenance",
        "@@step Optimizing the database", "@@done 0 Optimizing the database",
        "@@step Cleaning system logs", "@@done 0 Cleaning system logs",
        "@@step Restarting Koha services", "@@done 0 Restarting Koha services",
        "@@msg ok OK\tMaintenance completed successfully!",
    ],
    "reports-install": [
        "@@preview Preview (dry run)\t● Overdue loans with patron contacts — new\\n● Lost items — update",
        "@@ask Essential reports pack\tNew reports: 1\\nReports to update: 1\\n\\nInstall them now?",
        "@@note Generating the backup...",
        "@@msg ok OK\t✅ Reports installed: 2",
    ],
    "reports-remove": [
        "@@preview Preview (dry run)\t● Overdue loans with patron contacts\\n● Lost items",
        "@@ask Essential reports pack\tRemove the 2 report(s) of the pack?",
        "@@note Generating the backup...",
        "@@msg ok OK\t✅ Reports removed: 2",
    ],
    "cloud-remote": ["@@note Testing the real cloud upload...",
                     "@@msg ok OK\tCloud enabled and tested successfully."],
}


async def demo_task(out: "TaskOutcome", name: str, args: tuple[str, ...], reporter: "Reporter | None",
                    on_result: Callable[[str, str], None] | None, env: dict[str, str]) -> "TaskOutcome":
    lines = _SCRIPTS.get(name)
    if lines is None:
        out.feed(f"@@msg error Error\tUnknown panel action: {name}", reporter)
        out.rc = 2
        return out
    pause = 0.0 if name in ("info", "cloud-remotes") else 0.15
    for line in lines:
        # KEI_TASK_ANSWER=no: the routine stops at its question, as in bash.
        if env.get("KEI_TASK_ANSWER") == "no" and out.asks:
            break
        out.feed(line.replace("{0}", args[0] if args else _HOME), reporter, on_result)
        if pause:
            await asyncio.sleep(pause)
    return out
