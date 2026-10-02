import re

from conftest import INSTALLER

from kei_panel.glyphs import GLYPH_ASCII, GLYPH_ICONS, plain_text, split_icon

TEXT = INSTALLER.read_text(encoding="utf-8")


def test_tables_match_the_installer():
    ascii_block = re.search(r"declare -A KEI_GLYPH_ASCII=\((.*?)\n\)", TEXT, re.S).group(1)
    assert dict(re.findall(r'\["([^"]+)"\]="([^"]*)"', ascii_block)) == GLYPH_ASCII
    icons_block = re.search(r"KEI_GLYPH_ICONS=\((.*?)\)\n", TEXT, re.S).group(1)
    assert tuple(re.findall(r'"([^"]+)"', icons_block)) == GLYPH_ICONS


def test_plain_text():
    assert plain_text("🔃  Toggle search engine (Zebra ⇄ Elasticsearch)") == \
        "Toggle search engine (Zebra <-> Elasticsearch)"
    assert plain_text("✅ ok") == "+ ok"


def test_split_icon():
    assert split_icon("💾  Backup center") == ("💾", "Backup center")
    assert split_icon("💾 Backup Center") == ("💾", "Backup Center")
    assert split_icon("Control Dashboard") == ("", "Control Dashboard")
    assert split_icon("高级 设置") == ("", "高级 设置")
