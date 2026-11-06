"""The Schedules center (Paulo, 2026-11-06): every job this server runs on
a schedule for Koha.Nexus, from every file that holds one, in one list.

Sources, each read as it is (nothing is written here):
- /etc/cron.d/koha_tasks: Koha's jobs, the cloud backups, the lines written
  by hand and the "# BEGIN ... # END" blocks; changed in the editor
  Schedules & cron tasks (views/crons.py);
- /etc/cron.d/koha-nexus-platform-backups: the backups of the platforms
  in containers (kei_backup_schedule), changed by "Schedule backups";
- /etc/cron.d/koha-nexus-backup-sets: the joint package of Koha and
  Tainacan (kei_set_schedule), changed by "Schedule the joint backup";
- the files the installer keeps for one job each (Elasticsearch and Zebra
  watchdogs, messaging, the OPAC sitemap, the free address heartbeat, the
  local AI at startup), and Koha's own package file: read only, each says
  which screen writes it;
- WP-Cron, WordPress's own scheduler inside Tainacan: it runs when the
  site gets visits, so it is shown as such, never as a server schedule.

A job is never listed twice: one row per cron line. When the same command
is scheduled in two lines, both rows say so. The last run comes only from
a reliable record (the backup logs, the newest package); without one the
row says "No run recorded". The next run is computed from the line, in the
server's time zone.
"""

from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import cron
from .i18n import t

CRON_DIR = "/etc/cron.d"
# KOHA, TAINACAN and SERVER are the platform filter's values; "" is all.
KOHA, TAINACAN, SERVER = "koha", "tainacan", "server"
PLATFORM_LABELS = {KOHA: "Koha", TAINACAN: "Tainacan", SERVER: "Server", "koha+tainacan": "Koha and Tainacan"}
BACKUP, MAINTENANCE, OTHER = "backup", "maintenance", "other"
KIND_LABELS = {BACKUP: "Backups", MAINTENANCE: "Maintenance and indexing", OTHER: "Other"}
NO_RECORD = "No run recorded"          # the same key as the Backup center: "Sem registro"

# The files of one job each the installer writes: (platform, kind, name,
# the section of the panel that changes it).
SYSTEM_FILES: dict[str, tuple[str, str, str, str]] = {
    "koha_es_watchdog": (KOHA, MAINTENANCE, "Elasticsearch indexer watchdog", "search"),
    "koha_zebra_queue": (KOHA, MAINTENANCE, "Zebra indexing watchdog", "search"),
    "koha_messaging": (KOHA, OTHER, "WhatsApp / Telegram notices", "hub"),
    "koha_sitemap": (KOHA, OTHER, "OPAC sitemap refresh", "opac"),
    "koha_kei_opac": (KOHA, OTHER, "OPAC carousel refresh (New arrivals and lists)", "opac"),
    "koha_broker": (SERVER, OTHER, "Free address heartbeat", "security"),
    "koha-easy-ollama": (SERVER, OTHER, "Local AI (Ollama) at startup", "ai"),
}
KOHA_PACKAGE = "koha-common"          # Debian's koha-common: Koha's own jobs
PLATFORM_FILE = "koha-nexus-platform-backups"
SET_FILE = "koha-nexus-backup-sets"
BOTH = "koha+tainacan"                 # a row of both platforms: shown under each filter
_SET_TASK = re.compile(r"--task\s+set-run\b")
TASKS_FILE = "koha_tasks"
_PLATFORM_TASK = re.compile(r"--task\s+platform-backup-(run|maintain|verify)\s+([a-z][a-z0-9-]*)")
PLATFORM_JOBS = {"run": "Backup", "maintain": "Backup upkeep (old packages and repository)",
                 "verify": "Restore test of an older backup"}
# Passwords or tokens written by hand in a command are not shown.
_SECRET = re.compile(r"(?i)(-p(?=[^\s-])|--password[= ]|\b(?:password|passwd|pass|token|secret|key)=)(\S+)")


@dataclass
class Row:
    """One scheduled job, as the center lists it."""
    platform: str            # koha | tainacan | server
    kind: str                # backup | maintenance | other
    name: str                # already translated
    when: str                # translated: "Daily at 23:00", "Every 5 minutes", the line as written
    state: str               # on | off | internal
    source: str              # the file (koha_tasks...) or "wp-cron"
    sched: str = ""          # the five cron fields or @word, "" for WP-Cron
    command: str = ""        # shown with any password hidden
    editor: str = ""         # where it is changed (a translated screen name)
    key: str = ""            # what the last run is looked up by ("koha:backup_sql"...)
    last: str = ""
    last_state: str = ""     # ok | bad | warn | ""
    next: str = ""
    also: list[str] = field(default_factory=list)   # other rows with the same command


# ----------------------------------------------------------------------
# Cron expressions
# ----------------------------------------------------------------------
_NAMES = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10,
          "nov": 11, "dec": 12, "sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}
_WORDS = {"@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *", "@weekly": "0 0 * * 0",
          "@daily": "0 0 * * *", "@midnight": "0 0 * * *", "@hourly": "0 * * * *"}
_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))


def _field(text: str, lo: int, hi: int) -> set[int] | None:
    """The values of one cron field ("*", "5", "1-5", "*/15", "10-50/10",
    "mon-fri", lists of these), or None when it cannot be read."""
    out: set[int] = set()

    def num(word: str) -> int:
        return _NAMES[word] if word in _NAMES else int(word)

    for part in text.lower().split(","):
        base, _sep, step_text = part.partition("/")
        if _sep and (not step_text.isdigit() or int(step_text) == 0):
            return None
        step = int(step_text) if _sep else 1
        try:
            if base == "*":
                a, b = lo, hi
            elif "-" in base:
                first, _dash, last = base.partition("-")
                a, b = num(first), num(last)
            else:
                a = num(base)
                b = hi if _sep else a
        except ValueError:
            return None
        if not (lo <= a <= b <= hi):
            return None
        out.update(range(a, b + 1, step))
    return out


def parse_schedule(sched: str) -> tuple[set[int], set[int], set[int], set[int], set[int], bool, bool] | None:
    """Minutes, hours, days of the month, months, weekdays (0-6), and
    whether the day of the month and the weekday were restricted."""
    sched = _WORDS.get(sched.strip().lower(), sched.strip())
    parts = sched.split()
    if len(parts) != 5:
        return None
    fields = [_field(p, lo, hi) for p, (lo, hi) in zip(parts, _RANGES)]
    if any(f is None for f in fields):
        return None
    minutes, hours, doms, months, dows = fields
    dows = {d % 7 for d in dows}
    return minutes, hours, doms, months, dows, parts[2] != "*", parts[4] != "*"


def next_run(sched: str, after: dt.datetime) -> dt.datetime | None:
    """The first minute after `after` the line runs at (cron's rule: when
    both the day of the month and the weekday are restricted, either one
    is enough). None for @reboot or a line that cannot be read."""
    parsed = parse_schedule(sched)
    if parsed is None:
        return None
    minutes, hours, doms, months, dows, dom_set, dow_set = parsed
    start = after.replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
    day = start.date()
    for _ in range(366 * 5):
        if day.month in months:
            in_dom, in_dow = day.day in doms, (day.weekday() + 1) % 7 in dows
            ok = (in_dom or in_dow) if (dom_set and dow_set) else (in_dom and in_dow)
            if ok:
                for h in sorted(hours):
                    for m in sorted(minutes):
                        when = dt.datetime(day.year, day.month, day.day, h, m)
                        if when >= start:
                            return when
        day += dt.timedelta(days=1)
    return None


def describe(sched: str) -> str:
    """The schedule in words, translated; the line as written otherwise."""
    s = sched.strip()
    if s.lower() == "@reboot":
        return t("At startup")
    s = _WORDS.get(s.lower(), s)
    parts = s.split()
    if len(parts) == 5:
        m, h, dom, mon, dow = parts
        if re.fullmatch(r"\*/\d+", m) and h == dom == mon == dow == "*":
            return t("Every ${n} minutes", n=m[2:])
        if m.isdigit() and h == dom == mon == dow == "*":
            return t("Every hour at :${m}", m=f"{int(m):02d}")
        if m.isdigit() and re.fullmatch(r"\*/\d+", h) and dom == mon == dow == "*":
            return t("Every ${n} hours at :${m}", n=h[2:], m=f"{int(m):02d}")
        if m.isdigit() and h.isdigit() and dom == mon == "*" and dow == "1-5" and int(m) < 60 and int(h) < 24:
            return t("Monday to Friday at ${time}", time=f"{int(h):02d}:{int(m):02d}")
    job = cron.Job("", "", "")
    cron._from_schedule(job, s)      # noqa: SLF001 - the editor's own reading of a line
    from .backup_center import when
    return when(job) if job.freq != "custom" else s


def server_timezone() -> str:
    """The time zone cron uses: the system's."""
    try:
        name = Path("/etc/timezone").read_text(encoding="utf-8").strip()
        if name:
            return name
    except OSError:
        pass
    try:
        target = os.readlink("/etc/localtime")
        if "zoneinfo/" in target:
            return target.split("zoneinfo/", 1)[1]
    except OSError:
        pass
    return dt.datetime.now().astimezone().tzname() or "UTC"


# ----------------------------------------------------------------------
# The files
# ----------------------------------------------------------------------
def screen(section_id: str) -> str:
    """A section's name as the sidebar shows it, without its icon."""
    from .glyphs import split_icon
    from .menus import section
    return split_icon(t(section(section_id).label))[1]


def hide_secrets(command: str) -> str:
    return _SECRET.sub(lambda m: m.group(1) + "***", command)


def _lines(text: str):
    """(on, schedule, command) of each job line of a cron file; "#off# "
    lines are jobs switched off in the editor."""
    for raw in text.splitlines():
        line = raw.strip()
        on = not line.startswith(cron.OFF.strip())
        body = line[len(cron.OFF.strip()):].strip() if not on else line
        if not body or (body.startswith("#")):
            continue
        m = cron._LINE.match(body)      # noqa: SLF001 - the same reading as the editor
        if m:
            yield on, m.group("sched"), m.group("cmd").strip()


def _short(command: str) -> str:
    cmd = re.sub(r"\s*[12]?>>?\s*/dev/null(\s+2>&1)?", "", command)
    cmd = re.sub(r"\s+2>&1", "", cmd).strip()
    return hide_secrets(cmd if len(cmd) <= 90 else cmd[:87] + "...")


def koha_task_rows(text: str, instance: str) -> list[Row]:
    """The lines of koha_tasks: only the ones in the file (the presets the
    editor offers but that are not written are not schedules)."""
    rows: list[Row] = []
    if not text.strip():
        return rows
    editor = screen("crons")
    cf = cron.parse(text, instance)
    for job in cf.jobs:
        if cron.run_command(job) not in text and job.command not in text:
            continue                     # a preset added by the editor, not in the file
        sched = job.schedule() if job.freq != "custom" else job.raw
        if cron.is_cloud(job):
            name = t("Cloud backup ${id}", id=cron.cloud_id(job)) + f" ({cron.WHAT_LABELS[cron.cloud_what(job)]})"
            platform, kind, key = KOHA, BACKUP, "koha:" + job.key
        elif job.key:
            name = t(job.label)
            platform = SERVER if job.key == "journal" else KOHA
            kind = BACKUP if job.key in ("backup_sql", "backup_marc") else \
                MAINTENANCE if job.key in ("reindex", "sessions", "plack", "journal", "mysqlcheck", "authorities") \
                else OTHER
            key = "koha:" + job.key
        else:
            name = t("Written by hand: ${cmd}", cmd=_short(job.command))
            platform, kind, key = SERVER, OTHER, ""
        rows.append(Row(platform, kind, name, describe(sched), "on" if job.enabled else "off", TASKS_FILE, sched,
                        hide_secrets(job.command), editor, key))
    # The "# BEGIN ... # END" blocks other screens keep in the file.
    for block in cf.blocks:
        title = block.splitlines()[0][len("# BEGIN "):].strip().capitalize()
        for on, sched, cmd in _lines(block):
            rows.append(Row(KOHA, OTHER, f"{title}: {_short(cmd)}", describe(sched), "on" if on else "off",
                            TASKS_FILE, sched, hide_secrets(cmd), screen("hub")))
    return rows


def platform_rows(text: str) -> list[Row]:
    """The backups of the platforms in containers (kei_backup_schedule)."""
    rows: list[Row] = []
    editor = screen("backups") + " > " + t("Schedule backups")
    for on, sched, cmd in _lines(text):
        m = _PLATFORM_TASK.search(cmd)
        if not m:
            continue
        job, pid = m.group(1), m.group(2)
        name = t(PLATFORM_JOBS[job])
        platform = TAINACAN if pid == TAINACAN else pid
        rows.append(Row(platform, BACKUP, name, describe(sched), "on" if on else "off", PLATFORM_FILE, sched,
                        hide_secrets(cmd), editor, f"{pid}:{job}"))
    return rows


def set_rows(text: str) -> list[Row]:
    """The scheduled joint package (kei_set_schedule): one line."""
    editor = screen("backups") + " > " + t("Schedule the joint backup")
    return [Row(BOTH, BACKUP, t("Joint backup (Koha + Tainacan)"), describe(sched), "on" if on else "off", SET_FILE,
                sched, hide_secrets(cmd), editor, "set:run")
            for on, sched, cmd in _lines(text) if _SET_TASK.search(cmd)]


def system_rows(name: str, text: str) -> list[Row]:
    platform, kind, label, section_id = SYSTEM_FILES[name]
    rows = []
    for on, sched, cmd in _lines(text):
        rows.append(Row(platform, kind, t(label), describe(sched), "on" if on else "off", name, sched,
                        hide_secrets(cmd), screen(section_id)))
    return rows


def koha_package_rows(text: str) -> list[Row]:
    """Koha's own jobs from its Debian package: read only."""
    rows = []
    for on, sched, cmd in _lines(text):
        script = re.search(r"/cronjobs/([\w./-]+\.pl)|/([\w-]+\.pl)", cmd)
        what = script.group(1) or script.group(2) if script else _short(cmd)
        rows.append(Row(KOHA, MAINTENANCE if "cleanup" in cmd or "index" in cmd else OTHER,
                        t("Koha package job: ${what}", what=what), describe(sched), "on" if on else "off",
                        KOHA_PACKAGE, sched, hide_secrets(cmd), t("Koha's own package (not changed by the panel)")))
    return rows


def wp_cron_row() -> Row:
    return Row(TAINACAN, OTHER, t("WP-Cron (WordPress's own scheduler)"),
               t("Runs when the site gets visits: it is not a server schedule"), "internal", "wp-cron",
               editor=t("Inside WordPress (not changed by the panel)"))


def read_files(cron_dir: str | Path = "") -> dict[str, str]:
    """The text of every file this center knows, from /etc/cron.d (or
    KEI_CRON_DIR in the tests); a missing file is left out."""
    base = Path(cron_dir or os.environ.get("KEI_CRON_DIR") or CRON_DIR)
    out: dict[str, str] = {}
    for name in (TASKS_FILE, PLATFORM_FILE, SET_FILE, KOHA_PACKAGE, *SYSTEM_FILES):
        path = base / name
        if name == TASKS_FILE and os.environ.get("KEI_CRON_FILE") and not cron_dir:
            path = Path(os.environ["KEI_CRON_FILE"])      # the editor's own file
        try:
            out[name] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return out


def collect(files: dict[str, str], instance: str, tainacan: bool) -> list[Row]:
    """Every row, in the order: Koha's tasks, the platforms' backups,
    the installer's own files, Koha's package, WP-Cron."""
    rows = koha_task_rows(files.get(TASKS_FILE, ""), instance)
    rows += platform_rows(files.get(PLATFORM_FILE, ""))
    rows += set_rows(files.get(SET_FILE, ""))
    for name in SYSTEM_FILES:
        if name in files:
            rows += system_rows(name, files[name])
    if KOHA_PACKAGE in files:
        rows += koha_package_rows(files[KOHA_PACKAGE])
    if tainacan:
        rows.append(wp_cron_row())
    mark_duplicates(rows)
    return rows


def _same(cmd: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\s*[12]?>>?\s*/dev/null(\s+2>&1)?|\s+2>&1", "", cmd)).strip()


def mark_duplicates(rows: list[Row]) -> None:
    """A command scheduled in two lines that are both on: each row names
    the other (cron runs it twice)."""
    by: dict[str, list[Row]] = {}
    for row in rows:
        if row.command and row.state == "on":
            by.setdefault(_same(row.command), []).append(row)
    for group in by.values():
        if len(group) > 1:
            for row in group:
                row.also = [f"{o.source}: {o.when}" for o in group if o is not row]


def fill_times(rows: list[Row], now: dt.datetime, last: dict[str, tuple[str, str]]) -> None:
    """The last run (from `last`, by row key) and the next one."""
    for row in rows:
        if row.state == "internal":
            row.next, row.last = "—", t(NO_RECORD)
            continue
        text, state = last.get(row.key, ("", "")) if row.key else ("", "")
        row.last, row.last_state = (text, state) if text else (t(NO_RECORD), "")
        if row.state != "on":
            row.next = t("Switched off")
            continue
        if row.sched.strip().lower() == "@reboot":
            row.next = t("At the next startup")
            continue
        when = next_run(row.sched, now)
        row.next = when.strftime("%Y-%m-%d %H:%M") if when else "—"


def set_last_run(value: str) -> tuple[str, str] | None:
    """kei_set_schedule_status's last=FINISHED|RESULT|RECOVERABILITY|COPY|FAILURES."""
    bits = (value or "").split("|")
    if len(bits) < 2 or not bits[0]:
        return None
    labels = {"ok": (t("OK"), "ok"), "partial": (t("INCOMPLETE"), "bad"), "failed": (t("FAILED"), "bad"),
              "busy": (t("Skipped (busy)"), "warn")}
    text, state = labels.get(bits[1], (bits[1], "warn"))
    if bits[1] == "ok" and len(bits) > 3 and bits[3] in ("failed", "refused"):
        text, state = t("OK, cloud copy FAILED"), "bad"
    return f"{bits[0][:16]} · {text}", state


def last_runs(backup: dict, plans, history, tainacan_backups, joint: str = "") -> dict[str, tuple[str, str]]:
    """The runs a reliable record says happened: the nightly SQL backup's
    log, each cloud backup's lines in the backup logs, the newest complete
    Tainacan package and the monthly restore test."""
    from .backup_center import plan_last_run
    out: dict[str, tuple[str, str]] = {}
    result = (backup or {}).get("last_result") or ""
    if result in ("ok", "failed", "skipped") and (backup or {}).get("log_epoch"):
        import time
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(int(backup["log_epoch"])))
        out["koha:backup_sql"] = (f"{stamp} · " + {"ok": t("OK"), "failed": t("FAILED"),
                                                     "skipped": t("Skipped (busy)")}[result],
                                  {"ok": "ok", "failed": "bad", "skipped": "warn"}[result])
    for plan in plans or []:
        h = plan_last_run(plan, history or [])
        if h is not None:
            out["koha:" + cron.CLOUD_PREFIX + plan.id] = (f"{h.when} · " + (t("OK") if h.ok else t("FAILED")),
                                                         "ok" if h.ok else "bad")
    if set_last_run(joint):
        out["set:run"] = set_last_run(joint)
    last = getattr(tainacan_backups, "last", "") or ""
    verified = getattr(tainacan_backups, "verified", "") or ""
    maintained = getattr(tainacan_backups, "maintained", "") or ""
    if last:
        created = last.partition("|")[2].partition("|")[0]
        if created:
            out["tainacan:run"] = (f"{created} · " + t("OK"), "ok")
    # kei_backup_status: verified = "DATE TIME PACKAGE ok|failed",
    # maintained = "DATE TIME ok|failed".
    for key, value in (("tainacan:verify", verified), ("tainacan:maintain", maintained)):
        bits = (value or "").split()
        if len(bits) >= 3 and bits[-1] in ("ok", "failed"):
            good = bits[-1] == "ok"
            out[key] = (f"{bits[0]} {bits[1][:5]} · " + (t("OK") if good else t("FAILED")), "ok" if good else "bad")
    return out


def platforms_offered(koha: bool, tainacan: bool) -> list[str]:
    """The platform filter's choices (besides All)."""
    return [p for p, on in ((KOHA, koha), (TAINACAN, tainacan), (SERVER, True)) if on]


def shown(rows: list[Row], platform: str = "", kind: str = "") -> list[Row]:
    return [r for r in rows if (not platform or platform in r.platform.split("+")) and (not kind or r.kind == kind)]
