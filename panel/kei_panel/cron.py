"""Koha's scheduled tasks (/etc/cron.d/koha_tasks) as data.

The "Schedules & cron tasks" screen (views/crons.py) shows every job as a
row: on or off, how often, at what time. This module reads the file into
Jobs and writes it back; `config.sh --task cron-apply FILE` checks the new
file, keeps a copy of the old one and puts it in place.

  * presets: the jobs the panel knows (the backups, the clean-ups, a full
    index rebuild, fines, authority linking), found by their command;
  * a job that is off stays in the file as "#off# <cron line>", so turning
    it on again keeps its time;
  * lines the library wrote by hand are kept as they are, with the comment
    right above them, and so are "# BEGIN ... / # END ..." blocks.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path

CRON_FILE = "/etc/cron.d/koha_tasks"
CRON_PATH = "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
OFF = "#off# "
REINDEX_BIN = "/usr/local/bin/koha-kei-reindex"

FREQS = {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly", "custom": "Custom"}
WEEKDAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")

HEADER = """# ======================================================================
# KOHA.NEXUS - SCHEDULED AUTOMATED TASKS
# ======================================================================
# This file controls Koha's periodic automated maintenance routines.
# It is written by the panel (Schedules & cron tasks): a job that is off
# starts with "#off# ". Lines you add by hand are kept.
#
# Schedule format:
# MIN HOUR DAY_OF_MONTH MONTH DAY_OF_WEEK(0=Sunday) USER COMMAND
#
# E-mail notices are not scheduled here: koha-common sends them once
# e-mail is enabled with "koha-email-enable"."""

_FIELD = r"[0-9*/,A-Za-z-]+"
_LINE = re.compile(rf"^(?P<sched>@\w+|{_FIELD}(?:\s+{_FIELD}){{4}})\s+(?P<user>[a-z_][a-z0-9_-]*)\s+(?P<cmd>\S.*)$")


@dataclass(frozen=True)
class Preset:
    key: str
    label: str
    command: str            # {instance} is the Koha instance
    match: str              # a job is this preset when its command contains it
    freq: str = "daily"
    day: int = 0
    hour: int = 0
    minute: int = 0
    enabled: bool = True
    freqs: tuple[str, ...] = tuple(FREQS)
    help: str = ""


PRESETS: tuple[Preset, ...] = (
    Preset("backup_sql", "Database backup (compressed SQL)", "/bin/bash /root/backup_sql.sh >/dev/null 2>&1",
           "backup_sql.sh", hour=23,
           help="Generates the .sql.gz file, checks it and sends it to the cloud when one is set."),
    Preset("backup_marc", "MARC21 records backup", "/bin/bash /root/backup_marc.sh >/dev/null 2>&1",
           "backup_marc.sh", freq="weekly", day=0, hour=3,
           help="Exports the catalogue and the authorities in MARC21."),
    Preset("reindex", "Full search index rebuild",
           REINDEX_BIN + " {instance} >/dev/null 2>&1", "koha-kei-reindex", freq="weekly", day=6, hour=2,
           enabled=False, help="Zebra or Elasticsearch, whichever Koha uses when it runs."),
    Preset("fines", "Fine calculation",
           '/usr/sbin/koha-shell {instance} -c "/usr/share/koha/bin/cronjobs/fines.pl" >/dev/null 2>&1',
           "fines.pl", hour=0, minute=45, enabled=False,
           help="Koha's fines.pl: charges the overdue fines of the circulation rules."),
    Preset("authorities", "Authority linking",
           '/usr/sbin/koha-shell {instance} -c "/usr/share/koha/bin/link_bibs_to_authorities.pl" >/dev/null 2>&1',
           "link_bibs_to_authorities.pl", freq="weekly", day=0, hour=4, enabled=False, freqs=("daily", "weekly"),
           help="Koha's link_bibs_to_authorities.pl: links the headings of the records to the authorities."),
    Preset("sessions", "Clear old sessions and the Zebra queue",
           '/usr/sbin/koha-shell {instance} -c "/usr/share/koha/bin/cronjobs/cleanup_database.pl --confirm '
           '--sessions --sessdays 2 --zebraqueue 10" >/dev/null 2>&1',
           "cleanup_database.pl", hour=1, minute=30, help="Keeps the database and the web pages responsive."),
    Preset("plack", "Plack restart (frees memory)", "/usr/sbin/koha-plack --restart {instance} >/dev/null 2>&1",
           "koha-plack --restart", hour=5),
    Preset("journal", "System log cleanup (keeps 14 days)", "/usr/bin/journalctl --vacuum-time=14d >/dev/null 2>&1",
           "journalctl --vacuum", minute=30),
    Preset("mysqlcheck", "Database table check",
           "/usr/bin/mysqlcheck --check --databases koha_{instance} >/dev/null 2>&1", "mysqlcheck",
           freq="monthly", day=5, hour=1),
)
BY_KEY = {p.key: p for p in PRESETS}


@dataclass
class Job:
    key: str                  # a preset's key, or "" for a line kept as written
    label: str
    command: str
    enabled: bool = True
    freq: str = "daily"
    day: int = 0              # weekday 0-6 (weekly) or day of the month 1-28 (monthly)
    hour: int = 0
    minute: int = 0
    raw: str = ""             # the schedule as written when freq is "custom"
    user: str = "root"
    note: list[str] = field(default_factory=list)   # comment lines above a kept line

    def schedule(self) -> str:
        """The five cron fields (or @word)."""
        if self.freq == "daily":
            return f"{self.minute} {self.hour} * * *"
        if self.freq == "weekly":
            return f"{self.minute} {self.hour} * * {self.day}"
        if self.freq == "monthly":
            return f"{self.minute} {self.hour} {self.day} * *"
        return self.raw

    def line(self) -> str:
        return (OFF if not self.enabled else "") + f"{self.schedule()} {self.user} {self.command}"

    def time(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"


def schedule_problem(text: str) -> str:
    """"" for five cron fields (or @daily...), else why not."""
    text = " ".join(str(text).split())
    if re.fullmatch(r"@(reboot|yearly|annually|monthly|weekly|daily|midnight|hourly)", text):
        return ""
    parts = text.split(" ")
    if len(parts) != 5:
        return "a schedule has five fields: minute hour day month weekday"
    limits = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))
    for part, (lo, hi) in zip(parts, limits):
        for item in part.split(","):
            m = re.fullmatch(r"(\*|\d+(?:-\d+)?)(?:/(\d+))?", item)
            if not m:
                if re.fullmatch(r"[A-Za-z]{3}(-[A-Za-z]{3})?", item):
                    continue
                return "a schedule has five fields: minute hour day month weekday"
            for n in re.findall(r"\d+", m.group(1)):
                if not lo <= int(n) <= hi:
                    return "a number of the schedule is out of range"
            if m.group(2) is not None and int(m.group(2)) == 0:
                return "a number of the schedule is out of range"
    return ""


def parse_time(text: str) -> tuple[int, int] | None:
    m = re.fullmatch(r"\s*(\d{1,2})[:h.](\d{2})\s*", str(text))
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        return None
    return int(m.group(1)), int(m.group(2))


def _from_schedule(job: Job, sched: str) -> None:
    parts = sched.split()
    if len(parts) == 5 and parts[0].isdigit() and parts[1].isdigit() and parts[3] == "*" \
            and int(parts[0]) < 60 and int(parts[1]) < 24:
        m, h, dom, _mon, dow = parts
        if dom == "*" and dow == "*":
            job.freq, job.minute, job.hour = "daily", int(m), int(h)
            return
        if dom == "*" and dow.isdigit() and int(dow) <= 7:
            job.freq, job.minute, job.hour, job.day = "weekly", int(m), int(h), int(dow) % 7
            return
        if dow == "*" and dom.isdigit() and 1 <= int(dom) <= 28:
            job.freq, job.minute, job.hour, job.day = "monthly", int(m), int(h), int(dom)
            return
    job.freq, job.raw = "custom", " ".join(parts)


@dataclass
class CronFile:
    jobs: list[Job]
    env: list[str]            # VAR=value lines other than PATH
    blocks: list[str]         # "# BEGIN ... # END" blocks, verbatim

    def job(self, key: str) -> Job | None:
        return next((j for j in self.jobs if j.key == key), None)


def preset_job(p: Preset, instance: str) -> Job:
    return Job(p.key, p.label, p.command.format(instance=instance), p.enabled, p.freq, p.day, p.hour, p.minute)


def parse(text: str, instance: str) -> CronFile:
    """The jobs of the file; every preset not in it is added, off (or with
    its default state when the file is empty)."""
    jobs: list[Job] = []
    env: list[str] = []
    blocks: list[str] = []
    note: list[str] = []
    block: list[str] | None = None
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.rstrip()
        if block is not None:
            block.append(line)
            if line.startswith("# END "):
                blocks.append("\n".join(block))
                block = None
            continue
        if line.startswith("# BEGIN "):
            block, note = [line], []
            continue
        if not line.strip():
            note = []
            continue
        enabled = not line.startswith(OFF)
        body = line[len(OFF):] if not enabled else line
        m = _LINE.match(body.strip())
        if m and not body.lstrip().startswith("#"):
            cmd = m.group("cmd").strip()
            preset = next((p for p in PRESETS if p.match in cmd and p.key not in seen), None)
            job = Job(preset.key if preset else "", preset.label if preset else "", cmd, enabled,
                      user=m.group("user"), note=[] if preset else note)
            _from_schedule(job, m.group("sched"))
            if preset:
                seen.add(preset.key)
            jobs.append(job)
            note = []
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", line):
            if not line.startswith("PATH="):
                env.append(line)
            continue
        if line.startswith("#"):
            note.append(line)
            # The header (or any "# ====" banner) is not a job's note.
            if line.startswith("# ===="):
                note = []
            continue
        note = []        # anything else is dropped: cron would refuse it anyway
    if block:
        blocks.append("\n".join(block + ["# END"]))
    empty = not jobs
    for p in PRESETS:
        if p.key not in seen:
            job = preset_job(p, instance)
            job.enabled = p.enabled if empty else False
            jobs.append(job)
    if not any(e.startswith("MAILTO=") for e in env):
        env.insert(0, 'MAILTO=""')
    return CronFile(jobs, env, blocks)


def defaults(instance: str) -> CronFile:
    return parse("", instance)


def describe(job: Job) -> str:
    """"Daily at 23:00", "Weekly, Sunday at 03:00", "0 */2 * * *"."""
    if job.freq == "daily":
        return f"Daily at {job.time()}"
    if job.freq == "weekly":
        return f"Weekly, {WEEKDAYS[job.day % 7]} at {job.time()}"
    if job.freq == "monthly":
        return f"Monthly, day {job.day} at {job.time()}"
    return job.raw


def render(cf: CronFile) -> str:
    out = [HEADER, CRON_PATH, *cf.env, ""]
    order = {p.key: i for i, p in enumerate(PRESETS)}
    known = sorted((j for j in cf.jobs if j.key), key=lambda j: order.get(j.key, 99))
    for job in known:
        out += [f"# {job.label} - {describe(job)}", job.line(), ""]
    for job in (j for j in cf.jobs if not j.key):
        out += [*job.note, job.line(), ""]
    for block in cf.blocks:
        out += [block, ""]
    return "\n".join(out).rstrip("\n") + "\n"


def file_problem(text: str) -> str:
    """"" when every line is one cron accepts (what the task checks too)."""
    if not any(ln.startswith("PATH=") for ln in text.splitlines()):
        return "the PATH line is missing"
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", s):
            continue
        m = _LINE.match(s)
        if not m:
            return f"not a cron line: {s[:60]}"
        sp = schedule_problem(m.group("sched"))
        if sp:
            return f"{sp}: {s[:60]}"
    return ""


def write_temp(text: str) -> Path:
    """The new file for `--task cron-apply` (private until the task copies it)."""
    fd, name = tempfile.mkstemp(prefix="kei-cron-", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    return Path(name)


def read(path: str | Path = "") -> str:
    path = Path(path or os.environ.get("KEI_CRON_FILE") or CRON_FILE)
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def with_freq(job: Job, freq: str) -> Job:
    """The job moved to another frequency, with a sensible day."""
    if freq == job.freq:
        return job
    day = job.day
    if freq == "weekly":
        day = day % 7
    elif freq == "monthly":
        day = min(max(day, 1), 28)
    raw = job.raw or job.schedule()
    return replace(job, freq=freq, day=day, raw=raw)
