"""LanguageScreen: the first screen of a new installation.

config.sh lets the new panel ask the panel language (instead of its
whiptail box) when translation.conf has none. The choice is written the
way set_panel_language writes it, then the app exits with RESTART_CODE:
config.sh reloads the language and starts the panel again in it (texts and
key labels are translated when the app starts).
"""

from __future__ import annotations

import re
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from ..env import TRANSLATION_CONFIG, normalize_panel_language, plain_glyphs_wanted

RESTART_CODE = 3
DEFAULT = "pt-BR"

# English names for the entries the classic Windows console may not draw
# (its fonts have no Arabic, Chinese, Japanese or Korean): with plain glyphs
# the English name comes first, so the line is readable whatever the font.
ENGLISH_NAMES = {
    "ru-RU": "Russian",
    "uk-UA": "Ukrainian",
    "ar-Arab": "Arabic",
    "fa-Arab": "Persian",
    "vi-VN": "Vietnamese",
    "zh-Hans-CN": "Chinese (Simplified)",
    "ja-Jpan-JP": "Japanese",
    "ko-Kore-KP": "Korean",
}


def language_items(installer: Path | None) -> list[tuple[str, str]]:
    """PANEL_LANG_ITEMS of the installer: (code, name) pairs."""
    try:
        text = installer.read_text(encoding="utf-8") if installer else ""
    except OSError:
        text = ""
    m = re.search(r"^PANEL_LANG_ITEMS=\($(.*?)^\)", text, re.S | re.M)
    items = re.findall(r'"([^"]+)"\s+"([^"]+)"', m.group(1)) if m else []
    return items or [("en-GB", "English"), ("pt-BR", "Português (Brasil)")]


def option_label(code: str, name: str, plain: bool = False) -> str:
    """One line of the list: the name in its own language, with the English
    name in front when plain glyphs are wanted (classic console)."""
    english = ENGLISH_NAMES.get(code) if plain else None
    return f"{english} - {name}   ({code})" if english else f"{name}   ({code})"


def write_language(code: str, path: Path = TRANSLATION_CONFIG) -> None:
    """set_panel_language: KOHA_PANEL_LANG_FULL / KOHA_PANEL_LANG, other lines kept."""
    try:
        old = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        old = []
    keep = [ln for ln in old if not re.match(r"^\s*KOHA_PANEL_LANG(_FULL)?=", ln)]
    keep += [f'KOHA_PANEL_LANG_FULL="{code}"', f'KOHA_PANEL_LANG="{normalize_panel_language(code)}"']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(keep) + "\n", encoding="utf-8")


class LanguageScreen(Screen):
    BINDINGS = [Binding("escape", "pick_default", "pt-BR", show=False)]

    def __init__(self, installer: Path | None, conf: Path = TRANSLATION_CONFIG):
        super().__init__()
        self.items = language_items(installer)
        self.conf = conf

    def compose(self) -> ComposeResult:
        with Vertical(id="language-box"):
            yield Label("koha.nexus", id="language-title")
            yield Label("Select your language / Selecione o idioma:", classes="view-prompt")
            plain = plain_glyphs_wanted()
            yield OptionList(*[Option(option_label(code, name, plain), id=code) for code, name in self.items],
                             id="language-list")

    def on_mount(self) -> None:
        lst = self.query_one(OptionList)
        codes = [code for code, _ in self.items]
        lst.highlighted = codes.index(DEFAULT) if DEFAULT in codes else 0
        lst.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.choose(event.option.id or DEFAULT)

    def action_pick_default(self) -> None:
        self.choose(DEFAULT)

    def choose(self, code: str) -> None:
        try:
            write_language(code, self.conf)
        except OSError as e:
            self.app.notify(str(e), severity="error")
            return
        self.app.exit(return_code=RESTART_CODE)
