"""The Koha Nexus Control Center window (Phase A).

One resizable pywebview window (Microsoft Edge WebView2) with the control
panel's sections in a sidebar, read from panel/kei_panel/menus.py
(nexus_core.menucatalog), and a workspace on the right. The dashboard is
the Phase 1 status view. A card runs its routine in Debian through the task
engine (`koha-panel --task run ACTION`, no console): its steps, log and
results fill the task panel, and its questions open dialogs in the page,
whose answers go back to the routine (nexus_core.taskproto).

app.js calls the Api methods (window.pywebview.api.*); task events reach the
page through engine.EventPump as nexus.onEvents(batch). The status view
reads Debian through wsl.exe and never starts it; a routine does, as the
terminal panel always did.
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

# Every routine of the menu runs inside the window, silently, as
# `koha-panel --task run ACTION` (the installer's --task mode asks its
# questions as @@ lines, drawn here as dialogs; no terminal, no whiptail).
# These have a --task of their own, with result rows, named as the action.
OWN_TASKS: FrozenSet[str] = frozenset({"status", "validation-report"})
# Full-screen terminal programs (htop, Midnight Commander): they need a
# terminal by nature, so they open one.
TERMINAL_TOOLS: FrozenSet[str] = frozenset({"monitor", "mc"})


def ui_labels(t: Translate) -> Dict[str, str]:
    """The window's own words, translated once for app.js."""
    words = {
        "dashboard": "Dashboard",
        "terminal_panel": "Advanced: terminal panel",
        "terminal_hint": "Opens the classic control panel in a terminal window",
        "opens_terminal": "Opens a terminal window (a full-screen program)",
        "later": "Comes to this window in a later version",
        "not_ported": "This screen comes to this window in a later version.",
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
        "edit_later": "Editing files from this window comes in a later version.",
    }
    return {k: t(v) for k, v in words.items()}


class Api:
    """The methods app.js may call (window.pywebview.api.*). Attributes are
    private: pywebview exposes every public one to the page."""

    def __init__(self, monitor: HealthMonitor, actions: Actions, t: Translate,
                 debian_running: Callable[[], bool], sections: Optional[List[Dict[str, Any]]] = None,
                 engine: Any = None, panel_only: FrozenSet[str] = frozenset()):
        self._monitor = monitor
        self._actions = actions
        self._t = t
        self._debian_running = debian_running
        self._sections = sections or []
        self._engine = engine
        self._panel_only = panel_only
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
        return {"sections": self._sections, "terminal": sorted(TERMINAL_TOOLS),
                "later": sorted(self._panel_only), "labels": ui_labels(self._t)}

    def open_entry(self, action: str) -> Dict[str, Any]:
        """A card was clicked: its routine starts here, in the window. Only
        actions of the menu are accepted."""
        if self._kinds.get(action) != "native":
            return {"ok": False}
        if action in TERMINAL_TOOLS:
            self._actions.verb("Panel", "-Action", action)
            return {"ok": True, "how": "terminal"}
        if action in self._panel_only or self._engine is None:
            return {"ok": False, "how": "later"}
        task = self._engine.start(action) if action in OWN_TASKS else self._engine.start("run", [action])
        return {"how": "inline", **task}

    def terminal_panel(self) -> bool:
        self._actions.verb("Panel")
        return True

    # --- tasks ------------------------------------------------------------
    def answer(self, run_id: int, value: Any) -> bool:
        return bool(self._engine and self._engine.answer(int(run_id), value))

    def cancel(self, run_id: int) -> bool:
        return bool(self._engine and self._engine.cancel(int(run_id)))
