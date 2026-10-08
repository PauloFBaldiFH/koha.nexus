"""python3 -m kei_panel [--demo]"""

import argparse
import os
import sys
import traceback

from .env import PanelEnv, log_error
from .i18n import Translator, install


MAXIMIZE = "\x1b[9;1t"   # xterm window op: maximize (ignored where unsupported)


def maximize_window() -> None:
    """Asks the terminal for a maximized window before the panel draws.
    xterm-like terminals (GNOME Terminal, Konsole, xterm, PuTTY...) act on
    it; Windows Terminal is opened maximized by its launcher (wt.exe -M);
    the Linux console has no window. KEI_NO_MAXIMIZE=1 leaves it alone."""
    if os.environ.get("KEI_NO_MAXIMIZE") == "1" or os.environ.get("TERM", "") in ("", "linux", "dumb"):
        return
    try:
        fd = os.open("/dev/tty", os.O_WRONLY | os.O_NOCTTY)
    except OSError:
        return
    try:
        os.write(fd, MAXIMIZE.encode())
    except OSError:
        pass
    finally:
        os.close(fd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kei_panel", description="koha.nexus panel (Textual)")
    parser.add_argument("--demo", action="store_true",
                        help="simulate the installer: no root, no Koha needed")
    args = parser.parse_args(argv)
    env = PanelEnv.detect(demo=args.demo)
    # Before the app module is imported: its key bindings are labelled
    # with t() when their classes are created.
    install(Translator(env.lang, env.installer, env.plain))
    from .app import KohaPanelApp

    app = KohaPanelApp(env)
    maximize_window()
    app.run()
    # config.sh opens the classic panel when this is not 0 (a crash).
    return app.return_code or 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log_error(traceback.format_exc())
        raise
