"""The Backup center as data: which platforms it offers, and the automatic
backups ("plans") of each, from what the installer already reports.

The center (views/backups.py) shows one platform at a time: Koha,
Tainacan, or both as a set (only the installed ones; the set only when
both are). Each automatic backup is a row with
its own destination, frequency, retention, what is encrypted and its last
run; nothing here invents a run: with no reliable record the row says
"No record".

Sources, all existing (nothing new is scheduled by reading them):
  Koha       the nightly SQL and the weekly MARC21 of /etc/cron.d/koha_tasks
             (cron.py), KEEP_DAYS and the cloud backups of cloud_plans.conf
             (`--task cloud-status`), the last nightly run (--status-json)
  Tainacan   the platform backup engine (`--task platform-backup-status`):
             daily time, restic repository, cloud copy, retention
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import cloud, cron
from .i18n import t

KOHA, TAINACAN, BOTH = "koha", "tainacan", "both"
SCOPES = (KOHA, TAINACAN, BOTH)
SCOPE_LABELS = {KOHA: "Koha", TAINACAN: "Tainacan", BOTH: "Koha and Tainacan"}

NO_RECORD = "No run recorded"          # "Sem registro": no reliable history


def scopes(koha: bool, tainacan: bool) -> list[str]:
    """The platforms the center offers: the installed ones, Koha first,
    and the two as a set when both are installed."""
    return [s for s, on in ((KOHA, koha), (TAINACAN, tainacan), (BOTH, koha and tainacan)) if on]


def pick_scope(wanted: str, offered: list[str]) -> str:
    """The platform shown: the one asked for when it is offered, else the
    first offered, else "" (nothing installed)."""
    if wanted in offered:
        return wanted
    return offered[0] if offered else ""


@dataclass(frozen=True)
class PlanRow:
    """One automatic backup, as the center lists it."""
    name: str
    destination: str
    when: str
    keep: str
    encrypted: str
    last: str
    state: str = ""          # ok | warn | bad | "" (no record)


def when(job: cron.Job | None) -> str:
    """"Daily at 23:00", "Off", "Not scheduled" (translated)."""
    if job is None:
        return t("Not scheduled")
    if not job.enabled:
        return t("Off")
    if job.freq == "daily":
        return t("Daily at ${time}", time=job.time())
    if job.freq == "weekly":
        return t("Weekly, ${day} at ${time}", day=t(cron.WEEKDAYS[job.day % 7]), time=job.time())
    if job.freq == "monthly":
        return t("Monthly, day ${day} at ${time}", day=job.day, time=job.time())
    return job.raw


def plan_last_run(plan: cloud.Plan, history: list[cloud.History]) -> cloud.History | None:
    """The newest upload (or failed upload) of one cloud backup, from the
    backup logs: the lines of cloud_plan.sh carry "[ID]"; an older line
    without an id counts for the plan sending to that connection. The
    cleanup lines are not runs."""
    runs = [h for h in history if h.cloud and "cleanup" not in h.text and h.when]
    tagged = [h for h in runs if f"[{plan.id}]" in h.text]
    if not tagged:
        tagged = [h for h in runs if not re.search(r"\[[^\]]+\]", h.text)
                  and (f"{plan.remote}:" in h.text or f" on {plan.remote} " in h.text)]
    return max(tagged, key=lambda h: h.when) if tagged else None


def koha_plans(cron_file: cron.CronFile | None, cloud_status: dict, plans: list[cloud.Plan],
               remotes: list[cloud.Remote], history: list[cloud.History], backup: dict) -> list[PlanRow]:
    """Koha's automatic backups: the nightly SQL and weekly MARC21 made on
    this server, then each cloud backup (its own connection, folder,
    schedule and days kept in the cloud)."""
    rows: list[PlanRow] = []
    keep = cloud_status.get("keep_days") or "7"
    local = cloud_status.get("dir_sql") or "/var/backups/koha_sql"
    sql = cron_file.job("backup_sql") if cron_file else None
    result = (backup or {}).get("last_result") or ""
    last, state = NO_RECORD, ""
    if result in ("ok", "failed", "skipped") and (backup or {}).get("log_epoch"):
        import time
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(int(backup["log_epoch"])))
        last = f"{stamp} · " + {"ok": t("OK"), "failed": t("FAILED"), "skipped": t("Skipped (busy)")}[result]
        state = {"ok": "ok", "failed": "bad", "skipped": "warn"}[result]
    rows.append(PlanRow(t("Database backup (SQL)"), t("This server") + f" ({local})", when(sql),
                        t("${n} days on this server", n=keep), t("Not encrypted"), t(last) if last == NO_RECORD
                        else last, state))
    marc = cron_file.job("backup_marc") if cron_file else None
    rows.append(PlanRow(t("MARC21 package"), t("This server"), when(marc), t("${n} days on this server", n=keep),
                        t("Not encrypted"), t(NO_RECORD)))
    kinds = {r.name: r for r in remotes}
    for plan in plans:
        job = next((j for j in (cron.cloud_jobs(cron_file) if cron_file else []) if cron.cloud_id(j) == plan.id),
                   None)
        remote = kinds.get(plan.remote)
        encrypted = t("Encrypted by the connection (rclone crypt)") if remote and remote.encrypted \
            else t("Not encrypted")
        keep_cloud = t("Everything kept") if plan.keep == 0 else t("${n} days in the cloud", n=plan.keep)
        h = plan_last_run(plan, history)
        if h is not None:
            plan_last, plan_state = f"{h.when} · " + (t("OK") if h.ok else t("FAILED")), "ok" if h.ok else "bad"
        else:
            plan_last, plan_state = t(NO_RECORD), ""
        what = cron.WHAT_LABELS.get(cron.cloud_what(job), "") if job else ""
        rows.append(PlanRow(t("Cloud backup ${id}", id=plan.id) + (f" ({what})" if what else ""), plan.where(),
                            when(job), keep_cloud, encrypted, plan_last, plan_state))
    return rows


def tainacan_encryption(key: str, repo: str, copy_crypt: bool = False) -> str:
    """What a Tainacan backup encrypts, part by part (the engine's package
    format 2): never "encrypted" for the whole."""
    parts = [t("configuration encrypted with this server's key") if key
             else t("configuration not encrypted (readable by root only)")]
    parts.append(t("files encrypted in the restic repository") if repo else t("files not encrypted"))
    parts.append(t("database not encrypted"))
    if copy_crypt:
        parts.append(t("the cloud copy is encrypted by the connection (rclone crypt)"))
    return "; ".join(parts)


def tainacan_plans(backups, keep: str = "", remotes: list[cloud.Remote] | None = None) -> list[PlanRow]:
    """Tainacan's automatic backup: the engine's daily backup, its
    destination (this server, a restic repository, a cloud copy) and its
    retention."""
    if not getattr(backups, "known", False):
        return []
    where = [t("This server")]
    if backups.repo:
        where.append(t("restic repository") + f" {backups.repo}")
    if backups.copy:
        where.append(t("copy to") + f" {backups.copy}")
    schedule = t("Daily at ${time}", time=backups.schedule) if backups.schedule else t("Not scheduled")
    parts = (keep or "7 7 4 6").split()
    if len(parts) == 4:
        retention = t("last ${a}, ${b} daily, ${c} weekly, ${d} monthly", a=parts[0], b=parts[1], c=parts[2],
                      d=parts[3])
    else:
        retention = keep
    if backups.last:
        _name, _sep, rest = backups.last.partition("|")
        created = rest.partition("|")[0]
        last, state = f"{created} · " + t("OK"), "ok"
    else:
        last, state = t(NO_RECORD), ""
    copy_remote = backups.copy.partition(":")[0] if backups.copy else ""
    crypt = any(r.name == copy_remote and r.encrypted for r in (remotes or []))
    return [PlanRow(t("Tainacan backup"), " + ".join(where), schedule, retention,
                    tainacan_encryption(backups.key, backups.repo, crypt), last, state)]
