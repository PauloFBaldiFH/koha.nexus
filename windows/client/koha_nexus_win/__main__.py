"""python -m koha_nexus_win app [--hidden] [--smoke FILE] | tray | window | check | version

app      the Control Center: the window and the tray icon in one process
         (--hidden: only the icon, as at sign-in; the window opens from it)
tray     the same as `app --hidden`
window   the same as `app`; when the app already runs, its window is shown
check    prints the status view model as JSON (no window)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import List, Optional

from nexus_core import menucatalog
from nexus_core.langcache import Translator
from nexus_core.monitor import HealthMonitor

from . import __version__, config, viewmodel, winapi
from .actions import Actions
from .notify import WindowsNotifier, toast_app_id
from .store import JsonStateStore
from .wsl import WslRunner

APP_TITLE = "koha.nexus : A smart, free and easy-to-use assistant for library management"
REPO = Path(__file__).resolve().parents[3]


def _logging(paths: config.KohaPaths) -> None:
    try:
        paths.logs.mkdir(parents=True, exist_ok=True)
        name = paths.logs / time.strftime("python-client-%Y%m%d.log")
        logging.basicConfig(filename=str(name), level=logging.INFO, encoding="utf-8",
                            format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
    except (OSError, TypeError, ValueError):
        logging.basicConfig(level=logging.WARNING)


def _leaf(paths: config.KohaPaths):
    """koha.ico's largest frame, for the tray icon (None when unreadable)."""
    try:
        from PIL import Image

        img = Image.open(paths.icon)
        sizes = sorted(getattr(img, "ico").sizes()) if hasattr(img, "ico") else []
        if sizes:
            img.size = sizes[-1]
        return img.convert("RGBA")
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).warning("koha.ico could not be read", exc_info=True)
        return None


def _sections(paths: config.KohaPaths, t: Translator):
    """The panel's menu as sidebar data, and its panel-only actions."""
    found = menucatalog.find_menus(paths.bin, REPO)
    if found is None:
        logging.getLogger(__name__).warning("menus.py not found: the sidebar has only the dashboard")
        return [], frozenset()
    menus = menucatalog.load_menus(found)
    tr = t
    if t.code == "pt":
        for installer in (paths.bin / "installer", REPO / "installer"):
            if installer.is_file():
                text = installer.read_text(encoding="utf-8", errors="replace")
                tr = menucatalog.with_menu_pt(t, menucatalog.menu_pt(text))
                break
    return menucatalog.catalog(menus, tr), menucatalog.panel_only(menus)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="koha_nexus_win", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=("app", "tray", "window", "check", "version"))
    ap.add_argument("--hidden", action="store_true", help="start with only the tray icon")
    ap.add_argument("--smoke", type=Path, help="CI: open, run one task, write a report, quit")
    args = ap.parse_args(argv)
    if args.command == "version":
        print(__version__)
        return 0

    paths = config.paths()
    _logging(paths)
    store = JsonStateStore(paths.state)
    t = Translator.load(paths.lang, winapi.ui_culture(), str(paths.root))
    runner = WslRunner()
    actions = Actions(paths, store.load)
    notifier = WindowsNotifier(paths.logs, lambda: toast_app_id(bool(store.load().get("appIdShortcut"))))

    if args.command == "check":
        monitor = HealthMonitor(runner, notifier, store, t=t, uptime_ms=winapi.uptime_ms, start_grace=False)
        st = monitor.status()
        print(json.dumps(viewmodel.build(st, runner.running(), t), indent=2, ensure_ascii=False))
        return 0

    from .app import run_app, signal_running_app
    from .tray import Tray
    from .window import Api

    hidden = args.hidden or args.command == "tray"
    mutex = winapi.NamedMutex(config.TRAY_MUTEX)
    if not mutex.acquire():
        if not hidden and signal_running_app():
            logging.getLogger(__name__).info("the app already runs: its window was asked to show")
        else:
            logging.getLogger(__name__).info("another Koha tray is running; this one ends")
        return 0
    try:
        store.save({"trayClosed": False})
        sections, panel_only = _sections(paths, t)
        tray_monitor = HealthMonitor(runner, notifier, store, t=t, uptime_ms=winapi.uptime_ms)
        tray = Tray(tray_monitor, actions, t, store.load, store.save, leaf=_leaf(paths), ask=winapi.ask)
        notifier.balloon = lambda title, text: tray.icon.notify(text, title) if tray.icon else None
        window_monitor = HealthMonitor(runner, notifier, store, t=t, uptime_ms=winapi.uptime_ms, start_grace=False)
        api = Api(window_monitor, actions, t, runner.running, sections=sections, panel_only=panel_only)
        run_app(api, tray, t(APP_TITLE), paths.logs, start_hidden=hidden, smoke=args.smoke)
    finally:
        mutex.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
