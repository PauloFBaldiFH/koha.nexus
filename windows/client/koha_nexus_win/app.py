"""The Control Center app: the tray icon and the window in one process.

pywebview's GUI loop needs the main thread, so it gets it; pystray runs its
own message loop on a second thread (Tray.start_in_thread). Closing the
window hides it: the app, its running task and the icon stay. The icon's
"Service status" (and a second start of the app, through a named event)
shows the window again; "Close this icon" ends both.

`--smoke FILE` (CI on a Windows runner) opens the window, starts one task
through the engine and the event pump, waits until the page has drawn the
sidebar and received the task's end, writes what it saw to FILE as JSON and
quits. It is how Phase A proves the two loops live together.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from nexus_core.monitor import HealthMonitor

from . import config, winapi
from .engine import Engine, EventPump
from .window import UI, Api

log = logging.getLogger(__name__)

SHOW_EVENT = "Local\\KohaNexusShowWindow"


def js_call(function: str, payload: Any) -> str:
    """The script that hands payload to a page function: JSON-encoded and
    ASCII-only, so no text from Debian is ever read as code."""
    return f"{function}({json.dumps(payload, ensure_ascii=True)})"


class ControlCenter:
    def __init__(self, api: Api, tray: Any, title: str, logs: Path, start_hidden: bool = False):
        self.api = api
        self.tray = tray
        self.title = title
        self.logs = logs
        self.start_hidden = start_hidden
        self.window: Any = None
        self.quitting = False
        self.pump: Optional[EventPump] = None
        self.engine: Optional[Engine] = None
        self.show_event = winapi.NamedEvent(SHOW_EVENT)

    # --- window -----------------------------------------------------------
    def show(self) -> None:
        if self.window is not None:
            self.window.show()
            try:
                self.window.restore()
            except Exception:  # noqa: BLE001 - not minimized
                pass

    def quit(self) -> None:
        if self.quitting:
            return
        self.quitting = True
        if self.pump:
            self.pump.stop()
        self.show_event.close()
        if self.window is not None:
            self.window.destroy()

    def _closing(self) -> bool:
        """The window's X hides it; only quit() really closes it."""
        if self.quitting:
            return True
        self.window.hide()
        return False

    def _deliver(self, batch: List[Dict[str, Any]]) -> None:
        if self.window is not None and not self.quitting:
            self.window.evaluate_js(js_call("nexus.onEvents", batch))

    def _watch_show_event(self) -> None:
        while not self.quitting:
            if self.show_event.wait(1000):
                self.show()

    # --- life -------------------------------------------------------------
    def run(self, smoke: Optional[Path] = None) -> None:
        import webview  # pywebview, Windows: EdgeChromium (WebView2)

        self.pump = EventPump(self._deliver)
        self.engine = Engine(self.pump.push, log_dir=self.logs / "tasks")
        self.api.set_engine(self.engine)
        self.window = webview.create_window(
            self.title, str(UI / "index.html"), js_api=self.api, width=1180, height=780,
            min_size=(860, 560), background_color="#18181B", hidden=self.start_hidden and smoke is None)
        self.window.events.closing += self._closing
        if self.tray is not None:
            self.tray.open_window = self.show
            self.tray.on_stop = self.quit

        def started() -> None:
            self.pump.start()
            if self.show_event.create():
                threading.Thread(target=self._watch_show_event, name="show-event", daemon=True).start()
            if self.tray is not None:
                self.tray.start_in_thread()
            if smoke is not None:
                self._smoke(smoke)

        webview.start(started, gui="edgechromium", private_mode=True)
        if self.tray is not None:
            self.tray.on_stop = None
            self.tray.stop()

    # --- CI proof -------------------------------------------------------
    def _smoke(self, out: Path, timeout: float = 90) -> None:
        result: Dict[str, Any] = {"ok": False}
        try:
            self.window.events.loaded.wait(30)
            result["page"] = self._poll("window.nexus && nexus.selfTest().ready", timeout=30)
            result["start"] = self.engine.start("status") if self.engine else None
            result["ended"] = self._poll("nexus.selfTest().ended", timeout=timeout)
            result["self_test"] = self.window.evaluate_js("nexus.selfTest()")
            icon = getattr(self.tray, "icon", None)
            result["tray"] = bool(icon is not None and getattr(icon, "visible", False))
            st = result["self_test"] or {}
            result["ok"] = bool(result["page"] and result["ended"] and st.get("sidebar", 0) >= 10 and result["tray"])
        except Exception as e:  # noqa: BLE001 - the report says what broke
            log.exception("smoke test failed")
            result["error"] = repr(e)
        out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        if self.tray is not None:
            self.tray.stop()
        else:
            self.quit()

    def _poll(self, expression: str, timeout: float) -> Any:
        end = time.time() + timeout
        while time.time() < end:
            try:
                value = self.window.evaluate_js(expression)
                if value:
                    return value
            except Exception:  # noqa: BLE001 - the page is still loading
                pass
            time.sleep(0.5)
        return None


def run_app(api: Api, tray: Any, title: str, logs: Path, start_hidden: bool,
            smoke: Optional[Path] = None) -> None:
    ControlCenter(api, tray, title, logs, start_hidden).run(smoke)


def signal_running_app() -> bool:
    """A second start: ask the app already running to show its window."""
    return winapi.NamedEvent(SHOW_EVENT).signal()
