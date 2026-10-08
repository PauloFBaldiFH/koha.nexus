"""The panel's colour theme: Flexoki by default, and the one chosen with
"Theme" in the command search (ctrl+p) kept for the next start.

The choice is one line in /etc/koha-easy-install/panel-theme.conf
(KEI_PANEL_THEME_FILE elsewhere, for the tests). A missing, unreadable or
unknown name gives the default; a file that cannot be written (demo mode,
not root) only means the choice is not kept.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from .env import CONFIG_DIR

DEFAULT_THEME = "flexoki"
THEME_FILE = CONFIG_DIR / "panel-theme.conf"


def theme_file() -> Path:
    return Path(os.environ.get("KEI_PANEL_THEME_FILE") or THEME_FILE)


def load_theme(available: Iterable[str]) -> str:
    try:
        name = theme_file().read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        name = ""
    return name if name in set(available) else DEFAULT_THEME


def save_theme(name: str) -> None:
    path = theme_file()
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(name + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
