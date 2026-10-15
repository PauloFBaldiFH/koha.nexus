"""python -m koha_nexus_win tray | window | check | version"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from typing import List, Optional

from nexus_core.langcache import Translator
from nexus_core.monitor import HealthMonitor

from . import __version__, config, viewmodel, winapi
from .actions import Actions
from .notify import WindowsNotifier, toast_app_id
from .store import JsonStateStore
from .wsl import WslRunner

APP_TITLE = "koha.nexus : A smart, free and easy-to-use assistant for library management"


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


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="koha_nexus_win", description=__doc__)
    ap.add_argument("command", choices=("tray", "window", "check", "version"))
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

    if args.command == "tray":
        from .tray import Tray

        mutex = winapi.NamedMutex(config.TRAY_MUTEX)
        if not mutex.acquire():
            logging.getLogger(__name__).info("another Koha tray is running; this one ends")
            return 0
        try:
            store.save({"trayClosed": False})
            monitor = HealthMonitor(runner, notifier, store, t=t, uptime_ms=winapi.uptime_ms)
            tray = Tray(monitor, actions, t, store.load, store.save, leaf=_leaf(paths), ask=winapi.ask)
            notifier.balloon = lambda title, text: tray.icon.notify(text, title) if tray.icon else None
            tray.run()
        finally:
            mutex.release()
        return 0

    from .window import Api, run

    mutex = winapi.NamedMutex(config.WINDOW_MUTEX)
    if not mutex.acquire():
        logging.getLogger(__name__).info("the Koha window is already open")
        return 0
    try:
        monitor = HealthMonitor(runner, notifier, store, t=t, uptime_ms=winapi.uptime_ms, start_grace=False)
        run(Api(monitor, actions, t, runner.running), t(APP_TITLE))
    finally:
        mutex.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
