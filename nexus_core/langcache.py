"""The panel's dictionaries (lang/<code>.cache), read the Windows way.

One "base64(English)|base64(translation)" line per text; "#" lines are
comments. Ported from windows/KohaEasy.Lang.psm1 (ConvertTo-KeiLanguageCode,
Import-KeiLanguage, T): placeholders are {0}, {1}..., and a translation
that lost or added one is ignored, so .format() never fails on a bad entry.
The Linux panel reads the same files with its own $VAR rules
(panel/kei_panel/i18n.py), which this module does not change.
"""

from __future__ import annotations

import base64
import binascii
import re
from pathlib import Path
from typing import Dict, Optional, Union

_PLACEHOLDER = re.compile(r"\{\d+\}")
_OLD_ROOT = "C:\\KohaEasy"


def language_code(culture: str) -> str:
    """Windows culture name (pt-BR, es-ES, fil-PH...) to dictionary code,
    with the rules of normalize_panel_language in the installer."""
    two = re.split(r"[-_]", (culture or "").lower())[0]
    return {"": "en", "fil": "tl", "nb": "no", "nn": "no"}.get(two, two)


def read_cache(path: Union[str, Path]) -> Dict[str, str]:
    """English text -> translation; {} when the file is missing."""
    out: Dict[str, str] = {}
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return out
    for line in lines:
        if line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) != 2:
            continue
        try:
            key = base64.b64decode(parts[0], validate=True).decode("utf-8")
            val = base64.b64decode(parts[1], validate=True).decode("utf-8")
        except (binascii.Error, ValueError):
            continue
        if val.strip():
            out[key] = val
    return out


class Translator:
    """t(text): the translation when its placeholders match, else the text.

    `root` is the Koha folder of this PC: texts name it C:\\KohaEasy (so the
    dictionaries keep their entries) and are shown with the real folder."""

    def __init__(self, entries: Optional[Dict[str, str]] = None, root: str = "", code: str = "en"):
        self.entries = entries or {}
        self.root = root
        self.code = code

    @classmethod
    def load(cls, lang_dir: Union[str, Path], culture: str, root: str = "") -> "Translator":
        code = language_code(culture)
        entries = {} if code == "en" else read_cache(Path(lang_dir) / f"{code}.cache")
        return cls(entries, root, code)

    def __call__(self, text: str) -> str:
        out = text
        tr = self.entries.get(text)
        if tr is not None and sorted(set(_PLACEHOLDER.findall(text))) == sorted(set(_PLACEHOLDER.findall(tr))):
            out = tr
        if self.root and self.root != _OLD_ROOT:
            out = out.replace(_OLD_ROOT, self.root)
        return out
