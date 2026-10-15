"""The notification-area icon (Phase 1 foundation of KohaEasy.Tray.ps1).

pystray draws the icon and its menu; a background thread runs
nexus_core.monitor.HealthMonitor every STATUS_EVERY_S seconds (sooner after
an action) and redraws the icon colour and the menu. Actions start the
existing KohaEasy.ps1 verbs (actions.py).

Not yet here, and the reason this tray is not the default: the clean stop
of Koha when Windows shuts down (KohaSessionWindow in KohaEasy.Tray.ps1:
WM_ENDSESSION, SetProcessShutdownParameters, ShutdownBlockReasonCreate), the
disk-space watchdog and the Windows 11 promotion of the icon. Phase E adds
them before the switch lets librarians use it.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, Optional

from nexus_core.monitor import HealthMonitor
from nexus_core.state import NOT_INSTALLED, Translate, state_text

from . import config, menu
from .actions import Actions

log = logging.getLogger(__name__)

# Icon dot colours of KohaEasy.Tray.ps1 ($icons).
DOT = {
    "running": (46, 160, 67),
    "starting": (230, 170, 20),
    "not_responding": (210, 50, 45),
    "stopped": (140, 140, 140),
    "stopped_by_user": (140, 140, 140),
    NOT_INSTALLED: (140, 140, 140),
}


def icon_image(state: str, leaf: Any = None, size: int = 64):
    """The Koha leaf with a status dot in the lower right corner and a
    white ring, as New-DotIcon draws it; a plain dot without the leaf."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    colour = DOT.get(state, DOT[NOT_INSTALLED]) + (255,)
    if leaf is not None:
        n = int(round(size * 0.8))
        img.paste(leaf.resize((n, n)), (0, 0), leaf.resize((n, n)))
        d = size * 0.44
        x = size - d - 0.75
        ring = max(1.5, size / 12)
        draw.ellipse((x, x, x + d, x + d), fill=colour, outline=(255, 255, 255, 255), width=int(round(ring)))
    else:
        draw.ellipse((1, 1, size - 2, size - 2), fill=colour)
    return img


class Tray:
    def __init__(self, monitor: HealthMonitor, actions: Actions, t: Translate,
                 load_state: Callable[[], Dict[str, Any]], save_state: Callable[[Dict[str, Any]], None],
                 leaf: Any = None, ask: Callable[[str], bool] = lambda question: True,
                 open_window: Optional[Callable[[], None]] = None,
                 on_stop: Optional[Callable[[], None]] = None):
        self.monitor = monitor
        self.actions = actions
        self.t = t
        self.load_state = load_state
        self.save_state = save_state
        self.leaf = leaf
        self.ask = ask
        # In the Control Center (app.py) the window lives in this process:
        # "Service status" shows it, and closing the icon ends the app.
        self.open_window = open_window
        self.on_stop = on_stop
        self.state = "stopped"
        self.icon = None
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._next_wait = 0.0

    # --- menu --------------------------------------------------------
    def _run(self, key: str) -> None:
        """One menu click (KohaEasy.Tray.ps1's Add-Item scripts)."""
        if key in menu.VERB_OF:
            self.actions.verb(*menu.VERB_OF[key])
            self.check_in(menu.RECHECK_AFTER.get(key, 0))
        elif key == "window":
            if self.open_window is not None:
                self.open_window()
            else:
                self.actions.python_window()
        elif key == "staff":
            self.actions.staff()
        elif key == "opac":
            self.actions.opac()
        elif key == "backups":
            self.actions.backups()
        elif key == "autostart":
            mode = "manual" if self.load_state().get("autostart") == "logon" else "logon"
            self.actions.verb("SetAutostart", "-Mode", mode)
        elif key == "notify_backup":
            self.save_state({"notifyBackupOk": not bool(self.load_state().get("notifyBackupOk"))})
        elif key == "close":
            # The keep-alive task does not bring it back before the next sign-in.
            self.save_state({"trayClosed": True})
            self.stop()
        if self.icon is not None:
            self.icon.update_menu()

    def _items(self):
        import pystray

        def make(entry: menu.Entry):
            if entry.key == "-":
                return pystray.Menu.SEPARATOR

            def action(icon, item, e=entry):
                if e.confirm and not self.ask(e.confirm):
                    return
                self._run(e.key)

            # The menu is rebuilt from menu.entries() each time it opens
            # (pystray.Menu with a callable), so plain values are current.
            checked = None if entry.checked is None else (lambda item, v=entry.checked: v)
            return pystray.MenuItem(entry.text, action, checked=checked, enabled=entry.enabled,
                                    default=entry.default)

        return [make(e) for e in self._entries()]

    def _entries(self):
        return menu.entries(self.state, self.load_state(), self.t)

    # --- checks ------------------------------------------------------
    def check_in(self, seconds: float) -> None:
        self._next_wait = seconds
        self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                result = self.monitor.check()
                self.state = result.status.state
                if self.icon is not None:
                    self.icon.icon = icon_image(self.state, self.leaf)
                    self.icon.title = state_text(self.state, self.t)[:63]
                    self.icon.update_menu()
                wait = 10 if self.state == "starting" else config.STATUS_EVERY_S
            except Exception:  # noqa: BLE001 - a failed check must not end the tray
                log.exception("tray check failed")
                wait = config.STATUS_EVERY_S
            self._wake.wait(self._next_wait or wait)
            self._wake.clear()
            self._next_wait = 0.0

    # --- life --------------------------------------------------------
    def run(self) -> None:
        import pystray

        self.icon = pystray.Icon("Koha", icon_image(self.state, self.leaf), "Koha",
                                 menu=pystray.Menu(lambda: self._items()))
        threading.Thread(target=self._loop, name="koha-checks", daemon=True).start()
        self.icon.run()

    def start_in_thread(self) -> threading.Thread:
        """The icon's own message loop on a thread of its own, so the
        window's GUI loop keeps the main thread (pywebview needs it)."""
        thread = threading.Thread(target=self.run, name="koha-tray", daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self.icon is not None:
            self.icon.stop()
        if self.on_stop is not None:
            callback, self.on_stop = self.on_stop, None
            callback()
