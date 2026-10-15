"""The Notifier for Windows (Show-KohaNotification).

A Windows toast (windows-toasts, WinRT) under Koha's AppUserModelID once
the Koha Start-menu shortcut carries it, Windows PowerShell's before that;
when toasts are unavailable, the tray's balloon tip; and always one line in
logs\\notifications-YYYYMMDD.log, the same file the PowerShell tray writes.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from . import config

Balloon = Callable[[str, str], None]


def log_line(logs: Path, level: str, title: str, text: str, now: Optional[float] = None) -> None:
    """Write-KohaLog "[level] title: text" into notifications-YYYYMMDD.log."""
    now = time.time() if now is None else now
    try:
        logs.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
        name = time.strftime("notifications-%Y%m%d.log", time.localtime(now))
        with open(logs / name, "a", encoding="utf-8") as f:
            f.write(f"{stamp} | [{level}] {title}: {text}\n")
    except OSError:
        pass


def toast_app_id(app_id_shortcut: bool) -> str:
    return config.APP_ID if app_id_shortcut else config.TOAST_APP_ID


class WindowsNotifier:
    def __init__(self, logs: Path, app_id: Callable[[], str], balloon: Optional[Balloon] = None):
        self.logs = logs
        self.app_id = app_id
        self.balloon = balloon

    def _toast(self, title: str, text: str, level: str) -> None:
        from windows_toasts import Toast, ToastScenario, WindowsToaster  # Windows only

        toast = Toast([title, text])
        if level == "error":
            toast.scenario = ToastScenario.Reminder
        WindowsToaster(self.app_id()).show_toast(toast)

    def notify(self, title: str, text: str, level: str = "info") -> str:
        log_line(self.logs, level, title, text)
        try:
            self._toast(title, text, level)
            return "toast"
        except Exception:  # noqa: BLE001 - any WinRT failure falls back
            if self.balloon is not None:
                try:
                    self.balloon(title, text)
                    return "balloon"
                except Exception:  # noqa: BLE001
                    pass
            return "log"
