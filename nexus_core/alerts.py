"""Which notifications to show after a check, and what to remember.

Ported from Get-KohaNotifications and Format-KohaSize
(windows/KohaEasy.Core.psm1). Pure: decide_alerts() gets the previous state
word, this check's KohaStatus, the disk health (or None) and the saved
state, and returns the alerts plus the saved-state changes that make each
alert appear once. The caller shows the alerts and saves the changes.

Saved-state keys read (state.json on Windows): desired, autostart,
notifyBackupOk, lastBackupLogEpoch, firstSeen, lastStaleBackupWarn,
lastRecoveryNotice, lastRecoveryEpoch, lastDiskLevel, lastDiskWarn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from .state import NOT_RESPONDING, RUNNING, STARTING, STOPPED, KohaStatus, Translate, saved_int

INFO = "info"
WARNING = "warning"
ERROR = "error"

STALE_BACKUP_H = 36           # $Cfg.StaleBackupH
DAY_S = 86400
WEEK_S = 604800
DISK_CRITICAL_AGAIN_S = 21600  # a critical disk is told again every 6 hours


@dataclass(frozen=True)
class Alert:
    level: str                 # info | warning | error
    title: str
    text: str


@dataclass(frozen=True)
class DiskHealth:
    """The free space around Koha's disk, measured by the platform
    (Get-KohaDiskHealth on Windows: the drive holding ext4.vhdx)."""

    level: str                 # ok | low | critical
    message: str = ""


@dataclass
class Decision:
    alerts: List[Alert] = field(default_factory=list)
    changes: Dict[str, Any] = field(default_factory=dict)


def format_size(n: float) -> str:
    """Format-KohaSize: 1.5 GB, 12.0 MB, 1,024 KB (binary units)."""
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:,.1f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:,.1f} MB"
    return f"{n / 1024:,.0f} KB"


def decide_alerts(previous: str, status: KohaStatus, disk: Optional[DiskHealth],
                  saved: Mapping[str, Any], now: int, t: Translate = str,
                  stale_backup_h: int = STALE_BACKUP_H) -> Decision:
    out: List[Alert] = []
    changes: Dict[str, Any] = {"lastState": status.state}
    cur = status.state
    wanted = saved.get("desired") == "running"

    # Service events (only while the librarian wants Koha on).
    if wanted and previous and previous != cur:
        if cur == NOT_RESPONDING:
            out.append(Alert(ERROR, t("Koha is not responding"), t(
                "The library system stopped answering. Use Restart Koha in the tray menu; "
                "if it happens again, export the diagnostics for support.")))
        elif cur == STOPPED and previous in (RUNNING, STARTING):
            out.append(Alert(ERROR, t("Koha stopped unexpectedly"), t(
                "Koha was turned off without Stop Koha. It will be started again automatically.")))
        elif cur == RUNNING and previous in (NOT_RESPONDING, STOPPED):
            out.append(Alert(INFO, t("Koha is working again"), t(
                "The staff interface and the catalog are answering again.")))

    linux = status.linux

    # Nightly backup: one notification per new line of backup_sql.log.
    if linux is not None and "backup" in linux.raw:
        b = linux.backup
        last_log = saved_int(saved, "lastBackupLogEpoch")
        if b.log_epoch > last_log:
            changes["lastBackupLogEpoch"] = b.log_epoch
            if last_log > 0 or (now - b.log_epoch) < DAY_S:
                if b.last_result == "ok" and saved.get("notifyBackupOk"):
                    out.append(Alert(INFO, t("Backup completed"), t(
                        "The nightly backup of the catalog was saved ({0}).").format(format_size(b.last_size))))
                elif b.last_result == "failed":
                    out.append(Alert(ERROR, t("Backup FAILED"), t(
                        "The nightly backup of the catalog failed. Open the tray menu and export the "
                        "diagnostics for support.")))
        # No good backup for too long (in manual mode Koha may be off at 23:00).
        # Counted from the first time Koha was seen, so a new install is not warned.
        limit = stale_backup_h * 3600
        first = saved_int(saved, "firstSeen")
        if first <= 0:
            first = now
            changes["firstSeen"] = now
        age = now - b.last_epoch
        if (linux.koha_installed and age > limit and (now - first) > limit
                and (now - saved_int(saved, "lastStaleBackupWarn")) > DAY_S):
            changes["lastStaleBackupWarn"] = now
            text = t("There is no recent backup of the catalog. Use Control panel > Manual backup, "
                     "or keep Koha on at 23:00.")
            if saved.get("autostart") == "manual":
                text = t("There is no recent backup of the catalog. Koha starts only when you click "
                         "Koha - Start, and the nightly backup runs at 23:00 only while Koha is on.")
            out.append(Alert(WARNING, t("No recent backup"), text))

    # Repair after an unclean stop (a power cut, a forced shutdown): told
    # once when it starts and once when it ends, for repairs of the last week.
    if linux is not None and "recovery" in linux.raw:
        rec = linux.recovery
        recent = rec.epoch > 0 and (now - rec.epoch) < WEEK_S
        if recent and rec.state == "running" and rec.epoch > saved_int(saved, "lastRecoveryNotice"):
            changes["lastRecoveryNotice"] = rec.epoch
            out.append(Alert(WARNING, t("Koha was not shut down properly"), t(
                "The computer was turned off while Koha was running (for example, a power cut). Koha is "
                "checking its database and its search index; searches may be incomplete for a few minutes.")))
        if recent and rec.state == "done" and rec.epoch > saved_int(saved, "lastRecoveryEpoch"):
            changes["lastRecoveryEpoch"] = rec.epoch
            changes["lastRecoveryNotice"] = rec.epoch
            problems = []
            if rec.db == "errors":
                problems.append(t("the database check reported errors"))
            if rec.db == "unreachable":
                problems.append(t("the database did not start"))
            if rec.backup == "failed":
                problems.append(t("the new backup failed"))
            if rec.index == "failed":
                problems.append(t("the search index could not be rebuilt"))
            if not problems:
                out.append(Alert(INFO, t("Koha repaired itself"), t(
                    "The computer was turned off while Koha was running. Koha checked its database, made a "
                    "new backup and updated its search index. Everything is working.")))
            else:
                out.append(Alert(ERROR, t("Koha needs attention"), t(
                    "The computer was turned off while Koha was running, and the check afterwards found "
                    "problems: {0}. Export the diagnostics from the tray menu and send them to support."
                ).format("; ".join(problems))))

    # Disk space: on every level change, and a critical level again every 6 hours.
    if disk is not None:
        changes["lastDiskLevel"] = disk.level
        again = disk.level == "critical" and (now - saved_int(saved, "lastDiskWarn")) > DISK_CRITICAL_AGAIN_S
        if disk.level != "ok" and (disk.level != saved.get("lastDiskLevel") or again):
            changes["lastDiskWarn"] = now
            critical = disk.level == "critical"
            title = t("Disk space is critically low") if critical else t("Disk space is low")
            out.append(Alert(ERROR if critical else WARNING, title, disk.message))

    return Decision(out, changes)
