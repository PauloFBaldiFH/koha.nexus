"""Koha's state in one word, and its text.

Ported from Resolve-KohaState, Get-KohaBootGraceUntil and
Get-KohaStateText (windows/KohaEasy.Core.psm1). Pure functions: the caller
says whether the distro is installed and running, passes what
--status-json returned and the saved state (state.json on Windows), and
gets the word back.

States:
    running          Koha answers (--status-json state "ok")
    starting         not up yet, but it was started a moment ago or the
                     computer has just booted (the grace period)
    not_responding   up for a while and still not "ok"
    stopped_by_user  stopped, and the librarian asked for it
    stopped          stopped without being asked
    not_installed    no distro, or no Koha inside it
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from .status import LinuxStatus

RUNNING = "running"
STARTING = "starting"
NOT_RESPONDING = "not_responding"
STOPPED_BY_USER = "stopped_by_user"
STOPPED = "stopped"
NOT_INSTALLED = "not_installed"

STATES = (RUNNING, STARTING, NOT_RESPONDING, STOPPED_BY_USER, STOPPED, NOT_INSTALLED)
ON_STATES = (RUNNING, STARTING, NOT_RESPONDING)   # Stop, Restart, Rebuild index make sense

# $Cfg.StartWaitS and $Cfg.BootGraceS of KohaEasy.Core.psm1.
START_WAIT_S = 180
BOOT_GRACE_S = 45

Translate = Callable[[str], str]


def saved_int(saved: Mapping[str, Any], key: str) -> int:
    """[int64]$State.key: a missing or non-numeric value is 0."""
    v = saved.get(key)
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    try:
        return int(str(v))
    except (TypeError, ValueError):
        return 0


def resolve_state(*, installed: bool, running: bool, linux: Optional[LinuxStatus],
                  saved: Mapping[str, Any], now: int, grace_until: int = 0,
                  start_wait_s: int = START_WAIT_S) -> str:
    """One of STATES. Until `grace_until` (the first seconds after the
    computer starts) a Koha that should run and is not up yet is starting,
    not stopped or not responding: WSL, systemd and Koha's services take a
    while after a cold boot."""
    if not installed:
        return NOT_INSTALLED
    desired = saved.get("desired")
    grace = now < grace_until and desired != "stopped" and saved.get("autostart") != "manual"
    if not running:
        if desired == "stopped":
            return STOPPED_BY_USER
        if grace:
            return STARTING
        return STOPPED
    started_at = saved_int(saved, "startedAt")
    recent = grace or (started_at > 0 and (now - started_at) < start_wait_s)
    if linux is not None and linux.state == "ok":
        return RUNNING
    if linux is not None and linux.state == "not_installed":
        return NOT_INSTALLED
    if recent:
        return STARTING
    return NOT_RESPONDING


def boot_grace_until(uptime_ms: int, now: int, boot_grace_s: int = BOOT_GRACE_S) -> int:
    """When the boot grace ends: `boot_grace_s` after the computer started.
    `uptime_ms` may come from a 32-bit tick counter that wraps after 24.9
    days ([Environment]::TickCount on Windows), so a negative value is
    unwrapped first."""
    if uptime_ms < 0:
        uptime_ms += 4294967296
    return now - uptime_ms // 1000 + boot_grace_s


@dataclass(frozen=True)
class KohaStatus:
    """What one check found (Get-KohaStatus)."""

    state: str
    desired: str = ""
    autostart: str = ""
    linux: Optional[LinuxStatus] = None
    checked_at: int = 0


# English texts, the keys of lang/<code>.cache (t() translates them).
STATE_TEXTS = {
    RUNNING: "Koha is running",
    STARTING: "Koha is starting...",
    NOT_RESPONDING: "Koha is not responding",
    STOPPED_BY_USER: "Koha is stopped (you stopped it)",
    STOPPED: "Koha is stopped",
    NOT_INSTALLED: "Koha is not installed",
}


def state_text(state: str, t: Translate = str) -> str:
    """The tray's header line for a state; unknown states read as not installed."""
    return t(STATE_TEXTS.get(state, STATE_TEXTS[NOT_INSTALLED]))
