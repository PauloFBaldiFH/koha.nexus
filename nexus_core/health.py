"""The status window's component rows and banner.

Ported from ConvertFrom-KohaQuickCheck, ConvertTo-KohaServiceState,
Get-KohaHealthSummary, Get-KohaServiceStateText and Get-KohaServiceName
(windows/KohaEasy.Core.psm1). The PowerShell window reads each unit with
its own quick-check script; here the rows come from --status-json, which
already carries the same units ("services") and the staff page's HTTP code
("http.staff"), so one call feeds both the tray and the window.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .state import NOT_INSTALLED, STARTING, STOPPED_BY_USER, Translate, state_text
from .status import LinuxStatus

# What the window lists, in the order Koha needs them ($script:KohaServices).
SERVICES = (
    ("mariadb", "MariaDB"),
    ("apache2", "Apache"),
    ("rabbitmq-server", "RabbitMQ"),
    ("memcached", "Memcached"),
    ("koha-common", "Koha (koha-common)"),
)

RUNNING = "running"
STARTING_ROW = "starting"
FAILED = "failed"
STOPPED = "stopped"
UNKNOWN = "unknown"


def service_state(active: str) -> str:
    """systemctl is-active as running | starting | failed | stopped | unknown."""
    return {
        "active": RUNNING,
        "activating": STARTING_ROW,
        "reloading": STARTING_ROW,
        "failed": FAILED,
        "inactive": STOPPED,
        "deactivating": STOPPED,
    }.get(active, UNKNOWN)


@dataclass(frozen=True)
class Row:
    unit: str          # wsl | <systemd unit> | http
    name: str
    state: str         # running | starting | failed | stopped | unknown
    detail: str = ""


@dataclass(frozen=True)
class Summary:
    level: str                         # ok | starting | fault | stopped | unknown
    text: str
    broken: List[str] = field(default_factory=list)   # units shown in red


def component_rows(debian_running: bool, linux: Optional[LinuxStatus]) -> List[Row]:
    """Debian (WSL), the services, then the staff page. With Debian stopped
    nothing inside it runs, so every row reads stopped; with Debian up and
    no status (the verb failed), the services read unknown."""
    rows = [Row("wsl", "Debian (WSL)", RUNNING if debian_running else STOPPED)]
    for unit, name in SERVICES:
        state = STOPPED
        if debian_running:
            state = service_state(linux.service(unit)) if linux is not None else UNKNOWN
        rows.append(Row(unit, name, state))
    web, code = STOPPED, ""
    if debian_running:
        web = FAILED
        if linux is not None:
            code = str(linux.http_staff) if linux.http_staff else "000"
            if 100 <= linux.http_staff <= 499:
                web = RUNNING
    rows.append(Row("http", "staff", web, code))
    return rows


def row_name(row: Row, t: Translate = str) -> str:
    return t("HTTP response") if row.unit == "http" else row.name


def row_state_text(row: Row, t: Translate = str) -> str:
    if row.unit == "http":
        if row.state == RUNNING:
            return t("Answers (HTTP {0})").format(row.detail)
        if row.state == FAILED:
            return t("Does not answer")
    return t({RUNNING: "Running", STARTING_ROW: "Starting", FAILED: "Failed",
              STOPPED: "Stopped"}.get(row.state, "Unknown"))


def summarize(rows: List[Row], koha_state: str, t: Translate = str) -> Summary:
    """The banner: ok when every row runs, starting while Koha comes up,
    fault naming what is down, stopped when the librarian stopped Koha."""
    if koha_state in (NOT_INSTALLED, STOPPED_BY_USER):
        return Summary("stopped", state_text(koha_state, t))
    if not rows:
        return Summary("unknown", t("Checking..."))
    broken = [r for r in rows if r.state not in (RUNNING, STARTING_ROW)]
    starting = [r for r in rows if r.state == STARTING_ROW]
    if not broken and not starting:
        return Summary("ok", t("All services are running"))
    if koha_state == STARTING or not broken:
        # Koha is still coming up: the rows that are not up yet are not faults.
        return Summary("starting", state_text(STARTING, t))
    if not any(r.unit == "wsl" and r.state == RUNNING for r in rows):
        # Everything inside Debian is down with it: name only Debian.
        broken = [r for r in rows if r.unit == "wsl"]
    if len(broken) == 1:
        if broken[0].unit == "http":
            text = t("Attention: the staff interface does not answer")
        else:
            text = t("Attention: {0} is offline").format(broken[0].name)
    else:
        text = t("Attention: {0} components are offline ({1})").format(
            len(broken), ", ".join(row_name(r, t) for r in broken))
    return Summary("fault", text, [r.unit for r in broken])
