"""The tray's colour, its tooltip and one line per system (study 11, U7).

Ported to windows/KohaEasy.Core.psm1 (Resolve-KohaIndicator), which the
Windows tray runs; both follow the matrix of the study's section 11:

    green   every installed system that should run is answering
    yellow  something needs attention, the check is older than 10 minutes,
            the state could not be read, or the systems are starting
    red     a part a system needs is down (database, application, web
            server, Docker), or Debian stopped without being asked
    gray    no system installed, or stopped by the person

The Linux side computes "summary" once (kei_panel/status_summary.py); this
only reads it. An older installer has no summary: the tray then behaves as
before, from Koha's state word.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .state import NOT_INSTALLED, RUNNING, STARTING, STOPPED, STOPPED_BY_USER, Translate, state_text
from .status import LinuxStatus

GREEN, YELLOW, RED, GRAY = "green", "yellow", "red", "gray"
STALE_S = 600
TOOLTIP_MAX = 63                    # NotifyIcon.Text

# English keys of lang/<code>.cache, the same in the PowerShell port.
REASONS = {
    "stopped": "stopped",
    "database_stopped": "database stopped",
    "web_server_stopped": "web server stopped",
    "not_responding": "not responding",
    "services_partial": "some services stopped",
    "backup_failed": "last backup failed",
    "backup_late": "backup late",
    "installing": "installing",
    "install_failed": "installation failed",
    "docker_stopped": "Docker stopped",
    "not_running": "not running",
    "not_checked": "not checked yet",
    "unknown": "state unknown",
}
WORDS = {"ok": "running", "attention": "needs attention", "critical": "not working", "stopped": "stopped"}
COLOURS = {"ok": GREEN, "attention": YELLOW, "critical": RED}
ORDER = {"ok": 0, "attention": 1, "critical": 2}


@dataclass(frozen=True)
class Indicator:
    colour: str
    text: str                       # the header of the menu
    tooltip: str                    # the same, at most 63 characters
    lines: tuple = ()               # one per system: "Biblioteca Central (Koha): running"


def _fit(text: str) -> str:
    return text if len(text) <= TOOLTIP_MAX else text[:TOOLTIP_MAX - 1] + "…"


def _make(colour: str, text: str, lines=()) -> Indicator:
    return Indicator(colour, text, _fit(text), tuple(lines))


def system_line(s, t: Translate = str) -> str:
    what = t(REASONS.get(s.reason, "")) if s.reason in REASONS and s.state != "ok" else t(WORDS[s.state])
    system = {"koha": "Koha", "tainacan": "Tainacan", "dspace": "DSpace"}[s.id]
    who = s.name if s.name == system else f"{s.name} ({system})"
    return f"{who}: {what}"


def indicator(state: str, linux: Optional[LinuxStatus], now: int, t: Translate = str) -> Indicator:
    """`state` is resolve_state's word; `linux` what --status-json said
    (None when it could not be read)."""
    if state == STOPPED_BY_USER:
        return _make(GRAY, t("Systems stopped (you stopped them)"))
    if state == STOPPED:
        return _make(RED, t("Systems are stopped"))
    if state == STARTING:
        return _make(YELLOW, t("Systems are starting..."))
    summary = linux.summary if linux is not None else None
    if state == NOT_INSTALLED and summary is None:
        return _make(GRAY, state_text(NOT_INSTALLED, t))
    if linux is None:
        return _make(YELLOW, t("Could not check the state"))
    if summary is None:                    # an older installer: as before
        return _make(GREEN if state == RUNNING else RED, state_text(state, t))
    lines = [system_line(s, t) for s in summary.systems]
    age = now - summary.checked_at
    if summary.checked_at and age > STALE_S:
        return _make(YELLOW, t("Could not check the state (${n} min ago)").replace("${n}", str(age // 60)), lines)
    if summary.state == "none" or not summary.systems:
        return _make(GRAY, t("No system installed. Open the panel to install."))
    if summary.state == "stopped":
        return _make(GRAY, t("Systems stopped"), lines)
    counted = [s for s in summary.systems if s.state != "stopped"]
    worst = max(counted, key=lambda s: ORDER[s.state])
    if worst.state == "ok":
        if len(summary.systems) == 1:
            return _make(GREEN, t("${name} is running").replace("${name}", worst.name), lines)
        return _make(GREEN, t("All systems running"), lines)
    text = f"{worst.name}: " + t(REASONS.get(worst.reason, WORDS[worst.state]))
    if any(s.state == "ok" for s in summary.systems):
        text += " · " + t("others running")
    return _make(COLOURS[worst.state], text, lines)


__all__ = ["Indicator", "indicator", "system_line", "GREEN", "YELLOW", "RED", "GRAY"]
