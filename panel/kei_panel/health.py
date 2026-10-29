"""The dashboard's Health cards: facts the panel reads by itself, next to
--status-json (an installer older than the panel still gets them).

Every reader only reads and never raises: a fact it cannot get is None and
the card says so. The network checks have short timeouts and run in
threads, after the status cards are already on screen.
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

UA = "koha.nexus-panel"
BACKUP_DIRS = ("/var/backups/koha_sql", "/var/backups/koha_marc")   # DIR_SQL, DIR_MARC in the installer
UPDATE_URL = "https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer"
# Answers an SRU explain without asking any library's catalogue.
SRU_GATEWAY_URL = "https://sru.koha.nexus/sru/loc?version=1.1&operation=explain"
NET_TIMEOUT = 8.0
ERROR_WINDOW = 24 * 3600
LOG_TAIL = 1_000_000        # bytes read from the end of each log
UPDATE_CACHE_SECS = 3600    # GitHub is asked about a new panel at most once an hour

_update_cache: dict[str, tuple[float, str | None]] = {}


# ----------------------------------------------------------------------
# CPU
# ----------------------------------------------------------------------
def _cpu_times(text: str) -> tuple[int, int] | None:
    """(busy, total) jiffies from the "cpu" line of /proc/stat."""
    for line in text.splitlines():
        if line.startswith("cpu "):
            nums = [int(x) for x in line.split()[1:] if x.isdigit()]
            if len(nums) < 4:
                return None
            idle = nums[3] + (nums[4] if len(nums) > 4 else 0)   # idle + iowait
            return sum(nums[:8]) - idle, sum(nums[:8])
    return None


def cpu_busy(first: str, second: str) -> float | None:
    """Percent of CPU in use between two /proc/stat reads."""
    a, b = _cpu_times(first), _cpu_times(second)
    if not a or not b or b[1] <= a[1]:
        return None
    return 100.0 * (b[0] - a[0]) / (b[1] - a[1])


def read_cpu(sample: float = 0.5) -> dict | None:
    try:
        first = Path("/proc/stat").read_text()
        time.sleep(sample)
        second = Path("/proc/stat").read_text()
        load = os.getloadavg()[0]
    except (OSError, AttributeError):
        return None
    return {"cores": os.cpu_count() or 1, "busy": cpu_busy(first, second), "load": load}


# ----------------------------------------------------------------------
# Sizes
# ----------------------------------------------------------------------
def dir_size(path: str) -> tuple[int, int] | None:
    """(bytes, files) under a folder, None when it does not exist."""
    if not os.path.isdir(path):
        return None
    total = files = 0
    for root, _dirs, names in os.walk(path):
        for name in names:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
                files += 1
            except OSError:
                pass
    return total, files


def read_backup_dirs(dirs: tuple[str, ...] = BACKUP_DIRS) -> dict | None:
    found = [s for s in (dir_size(d) for d in dirs) if s]
    if not found:
        return None
    return {"bytes": sum(s[0] for s in found), "files": sum(s[1] for s in found)}


def read_db_size(instance: str) -> int | None:
    sql = ("SELECT IFNULL(SUM(data_length+index_length),0) FROM information_schema.tables "
           "WHERE table_schema = DATABASE()")
    try:
        out = subprocess.run(["koha-mysql", instance, "-B", "-N", "-e", sql], stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    text = out.stdout.strip()
    return int(float(text)) if out.returncode == 0 and re.fullmatch(r"\d+(\.\d+)?", text) else None


# ----------------------------------------------------------------------
# Errors in the logs
# ----------------------------------------------------------------------
_MONTHS = {m: i for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
                                       "Nov", "Dec"), 1)}
# Apache (and Koha's intranet/opac-error.log, which Apache writes):
# [Thu Oct 29 19:00:00.123456 2026] [cgi:error] [pid 1] ...
_APACHE = re.compile(r"^\[\w{3} (\w{3}) +(\d{1,2}) (\d\d):(\d\d):(\d\d)(?:\.\d+)? (\d{4})\] \[([^\]]*)\]")
# Koha's plack-error.log (Log4perl): [2026/10/29 19:00:00] [ERROR] ...
_LOG4PERL = re.compile(r"^\[?(\d{4})[/-](\d\d)[/-](\d\d)[ T](\d\d):(\d\d):(\d\d)\]?\s*\[?(\w+)\]?")
_SEVERE = {"error", "crit", "alert", "emerg", "fatal"}
# Perl warnings Koha's CGI scripts print by the thousand: not errors.
_NOISE = ("uninitialized value", "deprecated", "redefined")


def parse_error_line(line: str) -> float | None:
    """The time of a log line that reports an error, None for any other line."""
    m = _APACHE.match(line)
    if m:
        mon, day, hh, mm, ss, year, module = m.groups()
        level = module.rsplit(":", 1)[-1].lower()
        stamp = (int(year), _MONTHS.get(mon, 0), int(day), int(hh), int(mm), int(ss))
    else:
        m = _LOG4PERL.match(line)
        if not m:
            return None
        *parts, level = m.groups()
        level = level.lower()
        stamp = tuple(int(p) for p in parts)
    if level not in _SEVERE or any(n in line for n in _NOISE):
        return None
    try:
        return datetime(*stamp).timestamp()
    except ValueError:
        return None


def _tail(path: str, limit: int = LOG_TAIL) -> list[str]:
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - limit))
            data = f.read()
    except OSError:
        return []
    lines = data.decode("utf-8", "replace").splitlines()
    return lines[1:] if size > limit else lines   # the first one is cut


def count_errors(paths: list[str], now: float | None = None, window: int = ERROR_WINDOW) -> dict | None:
    """Errors of the last 24 h in these logs (and their .1 rotation):
    {"count", "last" (the newest line), "last_epoch"}; None when no log could
    be read."""
    now = time.time() if now is None else now
    count, last, last_epoch, readable = 0, "", 0.0, False
    for path in paths:
        for p in (path + ".1", path):
            if not os.path.isfile(p):
                continue
            readable = readable or os.access(p, os.R_OK)
            for line in _tail(p):
                when = parse_error_line(line)
                if when is None or now - when > window:
                    continue
                count += 1
                if when >= last_epoch:
                    last, last_epoch = line, when
    return {"count": count, "last": last, "last_epoch": last_epoch} if readable else None


def apache_logs() -> list[str]:
    return ["/var/log/apache2/error.log"]


def koha_logs(instance: str) -> list[str]:
    base = f"/var/log/koha/{instance}"
    return [f"{base}/plack-error.log", f"{base}/intranet-error.log", f"{base}/opac-error.log"]


def short_error(line: str, width: int = 70) -> str:
    """The message of a log line, without its time, level and pid."""
    text = re.sub(r"^(\[[^\]]*\]\s*)+", "", line).strip()
    text = re.sub(r"^AH\d+:\s*", "", text)
    return text if len(text) <= width else text[: width - 1] + "…"


# ----------------------------------------------------------------------
# Network
# ----------------------------------------------------------------------
def http_check(url: str, timeout: float = NET_TIMEOUT) -> dict:
    """{"code", "ms"} of a GET; code 0 when nothing answered."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https URLs)
            code = resp.status
    except urllib.error.HTTPError as e:
        code = e.code
    except (OSError, ValueError):
        code = 0
    return {"code": code, "ms": int((time.monotonic() - start) * 1000)}


def tunnel_host(status: dict) -> str:
    a = status.get("access") or {}
    return a.get("public_opac") or a.get("public_staff") or ""


# ----------------------------------------------------------------------
# Z39.50
# ----------------------------------------------------------------------
def read_z3950() -> dict | None:
    """The last test of the Z39.50 list (z3950-history.json): servers that
    returned a valid MARC record, servers tested, when the list was tested."""
    from . import z3950
    try:
        h = z3950.History()
    except Exception:  # a broken history file is not the dashboard's problem
        return None
    rows = [v for k, v in h.data.items() if not k.startswith("_") and isinstance(v, dict) and v.get("status")]
    if not rows:
        return {"ok": 0, "tested": 0, "when": h.tested}
    when = h.tested or max(int(v.get("when") or 0) for v in rows)
    return {"ok": sum(v.get("status") == "ok" for v in rows), "tested": len(rows), "when": when}


# ----------------------------------------------------------------------
# Updates
# ----------------------------------------------------------------------
def version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v or ""))


def parse_panel_version(text: str) -> str | None:
    m = re.search(r'^PANEL_VERSION="\s*([0-9][0-9.]*)"', text, re.M)
    return m.group(1) if m else None


def update_url(installer: Path | None) -> str:
    """UPDATE_URL of the installer in use (a fork updates from its own)."""
    try:
        head = installer.read_text(encoding="utf-8", errors="replace")[:20000] if installer else ""
    except OSError:
        head = ""
    m = re.search(r'^UPDATE_URL="(https://[^"]+)"', head, re.M)
    return m.group(1) if m else UPDATE_URL


def latest_panel_version(url: str, timeout: float = NET_TIMEOUT) -> str | None:
    """PANEL_VERSION of the installer on GitHub: only its first 16 KB are
    read (the version is near the top). Cached for an hour."""
    cached = _update_cache.get(url)
    if cached and time.time() - cached[0] < UPDATE_CACHE_SECS:
        return cached[1]
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-16383",
                                               "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https URL)
            found = parse_panel_version(resp.read(16384).decode("utf-8", "replace"))
    except (OSError, ValueError):
        return None
    _update_cache[url] = (time.time(), found)
    return found


def parse_apt_policy(text: str) -> tuple[str, str] | None:
    """(installed, candidate) from `apt-cache policy koha-common`."""
    inst = re.search(r"Installed:\s*(\S+)", text)
    cand = re.search(r"Candidate:\s*(\S+)", text)
    if not inst or not cand or inst.group(1) == "(none)":
        return None
    return inst.group(1), cand.group(1)


def read_koha_versions() -> tuple[str, str] | None:
    """Koha installed and the newest one apt knows. apt's lists are not
    refreshed here (that needs the network and root): a newer Koha shows
    after the next apt update, nightly or by hand."""
    try:
        out = subprocess.run(["apt-cache", "policy", "koha-common"], capture_output=True, text=True,
                             timeout=20, check=False, env=dict(os.environ, LC_ALL="C"))
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_apt_policy(out.stdout)


# ----------------------------------------------------------------------
# All of it
# ----------------------------------------------------------------------
@dataclass
class Health:
    cpu: dict | None = None
    db_size: int | None = None
    backups: dict | None = None
    apache_errors: dict | None = None
    koha_errors: dict | None = None
    tunnel: dict | None = None          # None: no tunnel set up
    sru: dict | None = None
    z3950: dict | None = None
    panel_latest: str | None = None
    koha: tuple[str, str] | None = None


async def collect(status: dict, instance: str, installer: Path | None) -> Health:
    """Every Health fact at once, each in its own thread."""
    host = tunnel_host(status)
    jobs = {
        "cpu": asyncio.to_thread(read_cpu),
        "db_size": asyncio.to_thread(read_db_size, instance),
        "backups": asyncio.to_thread(read_backup_dirs),
        "apache_errors": asyncio.to_thread(count_errors, apache_logs()),
        "koha_errors": asyncio.to_thread(count_errors, koha_logs(instance)),
        "sru": asyncio.to_thread(http_check, SRU_GATEWAY_URL),
        "z3950": asyncio.to_thread(read_z3950),
        "panel_latest": asyncio.to_thread(latest_panel_version, update_url(installer)),
        "koha": asyncio.to_thread(read_koha_versions),
    }
    if host:
        jobs["tunnel"] = asyncio.to_thread(http_check, f"https://{host}/")
    values = await asyncio.gather(*jobs.values(), return_exceptions=True)
    return Health(**{k: (None if isinstance(v, BaseException) else v) for k, v in zip(jobs, values)})


def demo_health(now: float | None = None) -> Health:
    now = time.time() if now is None else now
    return Health(cpu={"cores": 4, "busy": 12.5, "load": 0.42}, db_size=640_000_000,
                  backups={"bytes": 1_450_000_000, "files": 31},
                  apache_errors={"count": 0, "last": "", "last_epoch": 0},
                  koha_errors={"count": 2, "last": "[2026/10/02 10:14:03] [ERROR] Search timed out",
                               "last_epoch": now - 5400},
                  tunnel={"code": 200, "ms": 310}, sru={"code": 200, "ms": 420},
                  z3950={"ok": 18, "tested": 24, "when": int(now) - 2 * 86400},
                  panel_latest="1.4.1", koha=("24.11.05-1", "24.11.05-1"))
