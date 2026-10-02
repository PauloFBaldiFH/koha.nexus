"""Plain symbols for the classic Windows console and the Linux console.

A port of kei_plain_text (installer): the same tables, kept in step by
tests/test_glyphs.py, which reads them back from the installer.
"""

from __future__ import annotations

import unicodedata

GLYPH_ASCII = {
    "✔": "+", "✓": "+", "☑": "+", "✖": "x", "●": "*", "•": "*", "◆": "*",
    "⚠": "!", "→": "->", "⇄": "<->", "↔": "<->",
    "✅": "+", "❌": "x", "❗": "!", "🔹": "*", "⭐": "*",
    "🟢": "+", "🔴": "x", "⚪": "-", "⬜": "-",
}

GLYPH_ICONS = (
    "⚙", "ℹ", "↻", "↶", "▣", "▤", "▦", "⌁", "⌕", "☁", "◈", "◌", "◷", "⏱", "✦", "★", "⟳", "⇩", "✉", "✎",
    "✏", "📖", "📋", "🪄", "️",
    "⏰", "🆓", "🆔", "🆕", "🆙", "🌉", "🌍", "🌎", "🌐", "🎓", "🎭", "🏠", "🏥", "👑", "💡", "💬", "💾",
    "📂", "📄", "📅", "📇", "📈", "📊", "📏", "📑", "📚", "📜", "📝", "📡", "📤", "📥", "📦", "📧", "📱",
    "🔀", "🔁", "🔃", "🔄", "🔌", "🔍", "🔎", "🔏", "🔐", "🔑", "🔒", "🔖", "🔗", "🔙", "🔧", "🔨", "🕒",
    "🚧", "🚨", "🚪", "🚮", "🛑", "🧩", "🧪", "🧮", "🧰", "🧱", "🧹", "🧾", "🩺",
)


def plain_text(s: str) -> str:
    """s with the symbols replaced; an icon goes with the spaces after it."""
    if s.isascii():
        return s
    for g, a in GLYPH_ASCII.items():
        s = s.replace(g, a)
    for g in GLYPH_ICONS:
        s = s.replace(g + "  ", "").replace(g + " ", "").replace(g, "")
    return s


def split_icon(label: str) -> tuple[str, str]:
    """'💾  Backup center' -> ('💾', 'Backup center'); no icon -> ('', label).

    Menu labels keep their icon inside the English key (that is what the
    dictionaries are keyed by); the new layout draws the icon in its own
    column, so it is split off after translation."""
    head, sep, rest = label.partition(" ")
    if sep and head and all(unicodedata.category(c) in ("So", "Mn") for c in head):
        return head, rest.strip()
    return "", label
