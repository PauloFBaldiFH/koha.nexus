"""t(): the bash panel's translations, read from the same files.

Dictionaries are lang/<code>.cache, one "base64(english)|base64(translation)"
line per text, keyed by the English text exactly as t() receives it. For
Portuguese the _MENU_PT table inside the installer wins, as in bash.
A translation whose variables or printf markers differ from the English
text is ignored, so a broken entry shows English instead of garbage.
"""

from __future__ import annotations

import base64
import binascii
import re
from pathlib import Path

from .env import CONFIG_DIR
from .glyphs import plain_text, steady

_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def _vars(s: str) -> list[str]:
    return sorted(m.group(1) or m.group(3) for m in _VAR_RE.finditer(s))


def is_safe(src: str, val: str) -> bool:
    """_t_is_safe: same number of %, same variable names."""
    return src.count("%") == val.count("%") and _vars(src) == _vars(val)


def expand(s: str, values: dict[str, object]) -> str:
    """_t_expand: $VAR, ${VAR}, ${VAR:-default} from values (no eval)."""
    def sub(m: re.Match) -> str:
        name = m.group(1) or m.group(3)
        if name in values and str(values[name]) != "":
            return str(values[name])
        return m.group(2) or ""
    return _VAR_RE.sub(sub, s)


def load_cache(path: Path) -> dict[str, str]:
    table: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="ascii", errors="ignore").splitlines()
    except OSError:
        return table
    for line in lines:
        k, sep, v = line.strip().partition("|")
        if not sep:
            continue
        try:
            key = base64.b64decode(k, validate=True).decode("utf-8")
            val = base64.b64decode(v, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            continue
        if key and val:
            table[key] = val
    return table


def load_menu_pt(installer: Path | None) -> dict[str, str]:
    """The declare -A _MENU_PT=( ["en"]="pt" ... ) table of the installer."""
    if not installer:
        return {}
    try:
        text = installer.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    m = re.search(r"^declare -A _MENU_PT=\($(.*?)^\)", text, re.S | re.M)
    if not m:
        return {}
    return dict(re.findall(r'\["((?:[^"\\]|\\.)*)"\]="((?:[^"\\]|\\.)*)"', m.group(1)))


class Translator:
    def __init__(self, lang: str, installer: Path | None, plain: bool = False):
        self.lang = lang
        self.plain = plain
        self.table: dict[str, str] = {}
        self.menu_pt: dict[str, str] = {}
        if lang != "en":
            for candidate in self._candidates(lang, installer):
                if candidate.is_file() and candidate.stat().st_size > 0:
                    self.table = load_cache(candidate)
                    break
            if lang == "pt":
                self.menu_pt = load_menu_pt(installer)

    @staticmethod
    def _candidates(lang: str, installer: Path | None) -> list[Path]:
        # _find_translation_cache: downloaded copy, bundled copy, next to the script.
        found = [CONFIG_DIR / f"translations_{lang}.cache", CONFIG_DIR / "lang" / f"{lang}.cache"]
        if installer:
            found.append(installer.resolve().parent / "lang" / f"{lang}.cache")
        return found

    def __call__(self, src: str, **values: object) -> str:
        if not src:
            return ""
        res = src
        if self.lang != "en":
            if src in self.menu_pt:
                res = self.menu_pt[src]
            elif src in self.table and is_safe(src, self.table[src]):
                res = self.table[src]
        if self.plain:
            res = plain_text(res)
        res = steady(res)
        return expand(res, values) if "$" in res else res


# One translator for the running app (set by KohaPanelApp); English until then.
_current = Translator("en", None)


def install(translator: Translator) -> None:
    global _current
    _current = translator


def t(src: str, **values: object) -> str:
    return _current(src, **values)
