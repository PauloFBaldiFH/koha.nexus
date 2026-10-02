"""python3 -m kei_panel [--demo]"""

import argparse
import sys

from .env import PanelEnv
from .i18n import Translator, install


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

    return KohaPanelApp(env).run() or 0


if __name__ == "__main__":
    sys.exit(main())
