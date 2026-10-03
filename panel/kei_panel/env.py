"""Where the panel runs: installer path, language, glyph mode, instance.

Everything is read the way the bash panel reads it, so both panels agree
while they live side by side.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path("/etc/koha-easy-install")
TRANSLATION_CONFIG = CONFIG_DIR / "translation.conf"
INSTALLED_PANEL = Path("/usr/local/bin/config.sh")
REPO_INSTALLER = Path(__file__).resolve().parents[2] / "installer"
INSTANCE = "library"

# normalize_panel_language in the installer: the special cases; anything
# else keeps the part before "-" or "_".
_LANG_ALIASES = {
    "por": "pt", "eng": "en", "spa": "es", "fra": "fr", "fre": "fr", "deu": "de", "ger": "de",
    "ita": "it", "nld": "nl", "dut": "nl", "pol": "pl", "rus": "ru", "ukr": "uk", "jpn": "ja",
    "kor": "ko", "zho": "zh", "chi": "zh", "ara": "ar", "heb": "he", "fas": "fa", "per": "fa",
    "tur": "tr", "ces": "cs", "cze": "cs", "swe": "sv", "ind": "id", "fil": "tl", "tgl": "tl",
    "ben": "bn", "hin": "hi", "vie": "vi", "nb": "no", "nn": "no", "nor": "no", "cat": "ca",
}


def normalize_panel_language(code: str) -> str:
    """Koha language code (pt-BR, en, fil...) -> dictionary name (pt, en, tl...)."""
    if not code:
        return "pt"
    base = re.split(r"[-_]", code, maxsplit=1)[0]
    return _LANG_ALIASES.get(base, base)


def read_lang_conf(key: str, path: Path = TRANSLATION_CONFIG) -> str:
    """_read_lang_conf: last KEY=value line of translation.conf, quotes removed."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    value = ""
    for line in text.splitlines():
        m = re.match(r"""^\s*%s=["']?([A-Za-z0-9_-]*)["']?\s*$""" % re.escape(key), line)
        if m:
            value = m.group(1)
    return value


def _is_utf8() -> bool:
    for var in ("LC_ALL", "LC_CTYPE", "LANG"):
        val = os.environ.get(var)
        if val:
            return "utf-8" in val.lower() or "utf8" in val.lower()
    return False


def _is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def plain_glyphs_wanted() -> bool:
    """Same rule as the installer: KEI_PLAIN_GLYPHS wins; else non-UTF-8,
    the Linux console, or WSL outside Windows Terminal (classic conhost)."""
    forced = os.environ.get("KEI_PLAIN_GLYPHS")
    if forced in ("0", "1"):
        return forced == "1"
    if not _is_utf8() or os.environ.get("TERM") == "linux":
        return True
    return _is_wsl() and not os.environ.get("WT_SESSION")


def find_installer() -> Path | None:
    explicit = os.environ.get("KEI_INSTALLER")
    for p in ([Path(explicit)] if explicit else []) + [INSTALLED_PANEL, REPO_INSTALLER]:
        if p.is_file():
            return p
    return None


def inherited_lock_fd() -> int | None:
    """The panel lock descriptor handed down by config.sh (KEI_PANEL_LOCK_FD).

    config.sh takes the panel lock, then starts this app; routines started
    from here get the same descriptor, so they share the lock instead of
    refusing to run as "already running in another session"."""
    fd = os.environ.get("KEI_PANEL_LOCK_FD", "")
    if not fd.isdigit():
        return None
    try:
        os.fstat(int(fd))
    except OSError:
        return None
    return int(fd)


@dataclass
class PanelEnv:
    installer: Path | None
    lang: str
    plain: bool
    demo: bool = False
    instance: str = INSTANCE
    no_color: bool = field(default_factory=lambda: bool(os.environ.get("NO_COLOR")))
    lock_fd: int | None = field(default_factory=lambda: inherited_lock_fd())

    @classmethod
    def detect(cls, demo: bool = False) -> "PanelEnv":
        demo = demo or os.environ.get("KEI_PANEL_DEMO") == "1"
        code = os.environ.get("KOHA_PANEL_LANG") or read_lang_conf("KOHA_PANEL_LANG") \
            or read_lang_conf("KOHA_PANEL_LANG_FULL") or "pt-BR"
        return cls(installer=find_installer(), lang=normalize_panel_language(code),
                   plain=plain_glyphs_wanted(), demo=demo)

    def child_env(self) -> dict[str, str]:
        """Environment for the installer: the glyph choice travels with it,
        as the Windows window passes it (env KEI_PLAIN_GLYPHS=0|1)."""
        env = dict(os.environ)
        env["KEI_PLAIN_GLYPHS"] = "1" if self.plain else "0"
        env.pop("KEI_PANEL_LOCK_FD", None)
        if self.lock_fd is not None:
            env["KEI_PANEL_LOCK_FD"] = str(self.lock_fd)
        return env
