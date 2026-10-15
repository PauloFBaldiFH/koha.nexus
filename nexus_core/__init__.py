"""nexus_core: koha.nexus logic shared by every platform.

What a desktop client (the Windows tray and window today, others later)
needs to know about Koha, written once and tested on Linux:

  * status.py   reads `config.sh --status-json` (schema 1), the one JSON
                object the Linux side already prints for the Windows tray,
                the panel's dashboard and notify.py;
  * state.py    turns it into one word (running, starting, not_responding,
                stopped_by_user, stopped, not_installed) and its text;
  * alerts.py   decides which notifications to show after a check and what
                to remember so each is shown once;
  * ports.py    the small interfaces a platform implements (Runner,
                Notifier, StateStore);
  * monitor.py  HealthMonitor: one check from start to end, through ports.

Ported from windows/KohaEasy.Core.psm1 (Get-KohaLinuxStatus,
Resolve-KohaState, Get-KohaBootGraceUntil, Get-KohaStateText,
Get-KohaNotifications, Format-KohaSize), which stay the reference until the
Python tray replaces the PowerShell one.

Standard library only, Python 3.9+, and no platform imports (winreg,
ctypes.windll, pywin32, Textual): the same files run on Debian, Ubuntu and
Windows. No file of the installer or the panel imports this package yet.
"""

__all__ = ["alerts", "monitor", "ports", "state", "status"]
