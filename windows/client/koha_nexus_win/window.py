"""The status window (Phase 1 foundation of KohaEasy.Window.ps1).

pywebview opens ui/index.html in Microsoft Edge WebView2. app.js asks
Api.status() for the view model (viewmodel.build) every WINDOW_REFRESH_S
seconds and calls Api.act(key) for a button; every check runs in
pywebview's own worker thread, so the window never freezes. Like the
PowerShell window, it reads Debian through wsl.exe and never starts it:
only its Start button does.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict

from nexus_core.monitor import HealthMonitor
from nexus_core.state import Translate

from . import config, viewmodel
from .actions import Actions

log = logging.getLogger(__name__)
UI = Path(__file__).resolve().parent / "ui"

# Window button -> KohaEasy.ps1 verb.
VERB_OF = {
    "start": ("Start",),
    "restart": ("RestartServices",),
    "panel": ("Panel",),
    "terminal": ("Terminal",),
    "poweroff": ("SafeShutdown",),
}


class Api:
    """The methods app.js may call (window.pywebview.api.*)."""

    def __init__(self, monitor: HealthMonitor, actions: Actions, t: Translate,
                 debian_running: Callable[[], bool]):
        self._monitor = monitor
        self._actions = actions
        self._t = t
        self._debian_running = debian_running

    def status(self) -> Dict[str, Any]:
        try:
            st = self._monitor.status()
            return viewmodel.build(st, self._debian_running(), self._t)
        except Exception as e:  # noqa: BLE001 - shown in the banner instead of a blank window
            log.exception("window status failed")
            return {"error": str(e)}

    def act(self, key: str) -> bool:
        if key == "staff":
            self._actions.staff()
        elif key == "opac":
            self._actions.opac()
        elif key in VERB_OF:
            self._actions.verb(*VERB_OF[key])
        else:
            return False
        return True

    def refresh_every(self) -> int:
        return config.WINDOW_REFRESH_S


def run(api: Api, title: str) -> None:
    import webview  # pywebview, Windows: EdgeChromium (WebView2)

    webview.create_window(title, str(UI / "index.html"), js_api=api, width=820, height=720,
                          min_size=(560, 520), background_color="#18181B")
    webview.start(gui="edgechromium", private_mode=True)
