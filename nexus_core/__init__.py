"""nexus_core: koha.nexus logic shared by every platform.

What a desktop client (a future Python tray on any platform) needs to know about Koha, written once and tested on Linux:

  * status.py   reads `config.sh --status-json` (schema 1), the one JSON
                object the Linux side already prints for the Windows tray,
                the panel's dashboard and notify.py;
  * state.py    turns it into one word (running, starting, not_responding,
                stopped_by_user, stopped, not_installed) and its text;
  * alerts.py   decides which notifications to show after a check and what
                to remember so each is shown once;
  * ports.py    the small interfaces a platform implements (Runner,
                Notifier, StateStore);
  * monitor.py  HealthMonitor: one check from start to end, through ports;
  * health.py   the component rows and the one-line summary of the status
                window (Get-KohaHealthSummary);
  * langcache.py  reads lang/*.cache so a client speaks the installer's
                language.

Ported from windows/KohaEasy.Core.psm1 (Get-KohaLinuxStatus,
Resolve-KohaState, Get-KohaBootGraceUntil, Get-KohaStateText,
Get-KohaNotifications, Format-KohaSize), which stay the reference: the
PowerShell tray is what Windows runs.

Standard library only, Python 3.9+, and no platform imports (winreg,
ctypes.windll, pywin32, Textual): the same files run on Debian, Ubuntu and
Windows. The panel and the Linux install never import it.
"""

__all__ = ["alerts", "health", "langcache", "monitor", "ports", "state", "status"]
