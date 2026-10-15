"""The control panel's menu, read by a desktop client.

panel/kei_panel/menus.py holds the Textual panel's whole menu as data
(sections, entries, the --run action of each, their descriptions). It uses
only the standard library, so a client loads that very file, read-only, and
draws the same sections in the same order: a section added for Linux shows
up in the Windows window with no second list to keep. On Windows the file
is C:\\Koha\\bin\\panel\\kei_panel\\menus.py, which install.ps1 copies.

Labels are the installer's English texts, icon included; they are the keys
of the lang/*.cache dictionaries, and for Portuguese the installer's own
_MENU_PT table wins, as in bash and in the Textual panel (i18n.py).
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional, Tuple

Translate = Callable[[str], str]

_MODULE = "nexus_core._panel_menus"


def load_menus(path: Path) -> ModuleType:
    """menus.py as a module of its own (the panel package is not imported)."""
    spec = importlib.util.spec_from_file_location(_MODULE, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    # dataclasses looks the module up while it builds the classes.
    sys.modules[_MODULE] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(_MODULE, None)
        raise
    return module


def menu_pt(installer_text: str) -> Dict[str, str]:
    """The declare -A _MENU_PT=( ["en"]="pt" ... ) table (i18n.load_menu_pt)."""
    m = re.search(r"^declare -A _MENU_PT=\($(.*?)^\)", installer_text, re.S | re.M)
    if not m:
        return {}
    return dict(re.findall(r'\["((?:[^"\\]|\\.)*)"\]="((?:[^"\\]|\\.)*)"', m.group(1)))


def with_menu_pt(t: Translate, table: Dict[str, str]) -> Translate:
    """t, with the installer's Portuguese menu table taking precedence."""
    if not table:
        return t
    return lambda s: table[s] if s in table else t(s)


def split_icon(label: str) -> Tuple[str, str]:
    """("📦", "Install Koha server") from "📦  Install Koha server"; a label
    without a leading symbol keeps an empty icon."""
    head, sep, tail = label.partition(" ")
    if sep and head and not any(ch.isalnum() for ch in head):
        return head, tail.strip()
    return "", label.strip()


def _entry(menus: ModuleType, e: Any, t: Translate) -> Dict[str, Any]:
    icon, text = split_icon(t(e.label))
    describe = getattr(menus, "description", None)
    desc = describe(e) if describe else ""
    return {
        "action": e.action,
        "kind": e.kind,
        "icon": icon,
        "label": text,
        "description": t(desc) if desc else "",
        "confirm": t(e.confirm) if getattr(e, "confirm", "") else "",
    }


def catalog(menus: ModuleType, t: Translate = str) -> List[Dict[str, Any]]:
    """Every section, in the panel's order, as plain data for a page:
    id, icon, label, view, key, sidebar, parent and the visible entries."""
    out: List[Dict[str, Any]] = []
    for s in menus.SECTIONS:
        icon, text = split_icon(t(s.label))
        out.append({
            "id": s.id,
            "icon": icon or getattr(s, "icon", ""),
            "label": text,
            "view": s.view,
            "key": getattr(s, "key", ""),
            "sidebar": getattr(s, "sidebar", True),
            "parent": getattr(s, "parent", ""),
            "entries": [_entry(menus, e, t) for e in s.entries if not getattr(e, "hidden", False)],
        })
    return out


def panel_only(menus: ModuleType) -> frozenset:
    """Actions the installer has no --run routine for (menus.PANEL_ONLY)."""
    return frozenset(getattr(menus, "PANEL_ONLY", frozenset()))


def find_menus(bin_dir: Path, repo_root: Optional[Path] = None) -> Optional[Path]:
    """menus.py in an install (bin\\panel) or, when run from a checkout, in
    the repository's panel folder."""
    for base in (bin_dir, repo_root):
        if base is None:
            continue
        candidate = base / "panel" / "kei_panel" / "menus.py"
        if candidate.is_file():
            return candidate
    return None
