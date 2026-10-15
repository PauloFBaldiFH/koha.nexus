"""The Koha Nexus Control Center window (Phase A).

One resizable pywebview window (Microsoft Edge WebView2) with the control
panel's sections in a sidebar, read from panel/kei_panel/menus.py
(nexus_core.menucatalog), and a workspace on the right. The dashboard is
the Phase 1 status view. In Phase A an entry opens its routine in the
terminal panel (KohaEasy.ps1 Panel -Action NAME); the read-only ones in
INLINE_TASKS already run inside the window through the task engine, which
proves the path every section takes in Phase B.

app.js calls the Api methods (window.pywebview.api.*); task events reach the
page through engine.EventPump as nexus.onEvents(batch). Like the PowerShell
window, the window reads Debian through wsl.exe and never starts it: only
its Start button does.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional

from nexus_core.monitor import HealthMonitor
from nexus_core.state import Translate

from . import config, viewmodel
from .actions import Actions

log = logging.getLogger(__name__)
UI = Path(__file__).resolve().parent / "ui"

# Dashboard button -> KohaEasy.ps1 verb.
VERB_OF = {
    "start": ("Start",),
    "restart": ("RestartServices",),
    "panel": ("Panel",),
    "terminal": ("Terminal",),
    "poweroff": ("SafeShutdown",),
}

# Menu actions that already run inside the window: read-only tasks whose
# --task name is the menu action's own name.
INLINE_TASKS: FrozenSet[str] = frozenset({"status", "validation-report"})


def ui_labels(t: Translate) -> Dict[str, str]:
    """The window's own words, translated once for app.js."""
    words = {
        "dashboard": "Dashboard",
        "terminal_panel": "Advanced: terminal panel",
        "terminal_hint": "Opens the classic control panel in a terminal window",
        "opens_terminal": "Opens in the terminal panel",
        "runs_here": "Runs here",
        "not_ported": "This screen is in the terminal panel for now.",
        "open_terminal": "Open the terminal panel",
        "running": "Running...",
        "finished": "Finished",
        "failed": "Failed",
        "cancelled": "Cancelled",
        "cancel": "Cancel",
        "close": "Close",
        "show_log": "Show the log",
        "hide_log": "Hide the log",
        "yes": "Yes",
        "no": "No",
        "ok": "OK",
        "busy": "Another task is running. Wait for it to finish.",
        "results": "Results",
        "path": "Path in Debian",
        "edit_later": "Editing files from this window comes in a later version. Use the terminal panel.",
    }
    return {k: t(v) for k, v in words.items()}


class Api:
    """The methods app.js may call (window.pywebview.api.*). Attributes are
    private: pywebview exposes every public one to the page."""

    def __init__(self, monitor: HealthMonitor, actions: Actions, t: Translate,
                 debian_running: Callable[[], bool], sections: Optional[List[Dict[str, Any]]] = None,
                 engine: Any = None, panel_only: FrozenSet[str] = frozenset(),
                 inline: FrozenSet[str] = INLINE_TASKS):
        self._monitor = monitor
        self._actions = actions
        self._t = t
        self._debian_running = debian_running
        self._sections = sections or []
        self._engine = engine
        self._panel_only = panel_only
        self._inline = inline
        self._kinds = {e["action"]: e["kind"] for s in self._sections for e in s["entries"]}

    def set_engine(self, engine: Any) -> None:
        self._engine = engine

    # --- dashboard ----------------------------------------------------
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

    # --- sidebar and sections -------------------------------------------
    def sections(self) -> Dict[str, Any]:
        return {"sections": self._sections, "inline": sorted(self._inline), "labels": ui_labels(self._t)}

    def open_entry(self, action: str) -> Dict[str, Any]:
        """A card was clicked: run it here when it can, else open it in the
        terminal panel. Only actions of the menu are accepted."""
        if action not in self._kinds:
            return {"ok": False}
        if action in self._inline and self._engine is not None:
            return {"ok": True, "how": "inline", **self._engine.start(action)}
        if action in self._panel_only:
            self._actions.verb("Panel")
        else:
            self._actions.verb("Panel", "-Action", action)
        return {"ok": True, "how": "terminal"}

    def terminal_panel(self) -> bool:
        self._actions.verb("Panel")
        return True

    # --- tasks ------------------------------------------------------------
    def answer(self, run_id: int, value: Any) -> bool:
        return bool(self._engine and self._engine.answer(int(run_id), value))

    def cancel(self, run_id: int) -> bool:
        return bool(self._engine and self._engine.cancel(int(run_id)))
