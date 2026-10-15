"""HealthMonitor: one status check from start to end, through the ports.

The same steps as the PowerShell tray's timer (KohaEasy.Tray.ps1, Start-Check
and its tick) and Get-KohaStatus:

  1. is Koha's system installed and running (never starting it);
  2. if running, `config.sh --status-json`;
  3. the state word (state.resolve_state), with the boot grace;
  4. the alerts for what changed (alerts.decide_alerts), shown;
  5. the saved-state changes written back.

The caller decides how often to call check() (60 s in the tray) and when
to pass a DiskHealth (every 30 min in the tray).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .alerts import Alert, DiskHealth, decide_alerts
from .ports import Notifier, Runner, StateStore
from .state import BOOT_GRACE_S, KohaStatus, Translate, boot_grace_until, resolve_state
from .status import parse_status

STATUS_TIMEOUT_S = 60


@dataclass
class CheckResult:
    status: KohaStatus
    alerts: List[Alert] = field(default_factory=list)


class HealthMonitor:
    def __init__(self, runner: Runner, notifier: Notifier, store: StateStore, *,
                 t: Translate = str,
                 clock: Callable[[], float] = time.time,
                 uptime_ms: Optional[Callable[[], int]] = None,
                 grace_s: int = BOOT_GRACE_S,
                 start_grace: bool = True):
        self.runner = runner
        self.notifier = notifier
        self.store = store
        self.t = t
        self.clock = clock
        self.uptime_ms = uptime_ms
        self.grace_s = grace_s
        # The tray starts at sign-in: for its first seconds a Koha that is
        # not up yet reads as starting (the boot grace below covers a cold
        # boot, the monitor's own start covers Fast Startup, which keeps the
        # uptime). A one-off look (the Status window) passes start_grace=False.
        self.grace_until = self._now() + grace_s if start_grace else 0

    def _now(self) -> int:
        return int(self.clock())

    def status(self) -> KohaStatus:
        """Get-KohaStatus: one look, no alerts, nothing saved."""
        now = self._now()
        saved = self.store.load()
        grace = self.grace_until
        if self.uptime_ms is not None:
            grace = max(grace, boot_grace_until(self.uptime_ms(), now, self.grace_s))
        installed = self.runner.installed()
        running = installed and self.runner.running()
        linux = None
        if running:
            r = self.runner.verb(["--status-json"], timeout=STATUS_TIMEOUT_S)
            if r.code == 0:
                linux = parse_status(r.out)
        state = resolve_state(installed=installed, running=running, linux=linux,
                              saved=saved, now=now, grace_until=grace)
        return KohaStatus(state=state, desired=str(saved.get("desired") or ""),
                          autostart=str(saved.get("autostart") or ""), linux=linux, checked_at=now)

    def check(self, disk: Optional[DiskHealth] = None) -> CheckResult:
        """One tray tick: look, tell what changed, remember it."""
        status = self.status()
        saved = self.store.load()
        decision = decide_alerts(str(saved.get("lastState") or ""), status, disk, saved,
                                 now=self._now(), t=self.t)
        for a in decision.alerts:
            self.notifier.notify(a.title, a.text, a.level)
        self.store.save(decision.changes)
        return CheckResult(status, decision.alerts)
