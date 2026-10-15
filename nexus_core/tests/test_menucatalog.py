from pathlib import Path

import pytest

from nexus_core import menucatalog as mc

REPO = Path(__file__).resolve().parents[2]
MENUS = REPO / "panel" / "kei_panel" / "menus.py"


@pytest.fixture(scope="module")
def menus():
    if not MENUS.exists():
        pytest.skip("panel not in this checkout")
    return mc.load_menus(MENUS)


def test_menus_py_loads_on_its_own(menus):
    """Contract: the Windows window imports menus.py without the panel
    package or Textual, so it must stay standard-library only."""
    assert len(menus.SECTIONS) >= 20
    assert menus.SECTIONS[0].id == "dashboard"


def test_catalog_keeps_the_panel_order_and_hides_dormant_entries(menus):
    cat = mc.catalog(menus)
    assert [s["id"] for s in cat] == [s.id for s in menus.SECTIONS]
    by_id = {s["id"]: s for s in cat}
    actions = [e["action"] for e in by_id["library"]["entries"]]
    assert "marc-undo" in actions and "cutter" not in actions  # cutter is hidden
    backup = by_id["backup"]
    assert backup["icon"] == "💾" and backup["label"] == "Backup center"
    first = backup["entries"][0]
    assert first["description"] and first["kind"] in ("native", "interactive", "background", "view")
    assert by_id["vpn"]["sidebar"] is False and by_id["vpn"]["parent"] == "security"
    assert by_id["dashboard"]["icon"] == "📊"  # from Section.icon


def test_every_entry_has_a_description(menus):
    for s in mc.catalog(menus):
        for e in s["entries"]:
            assert e["description"], (s["id"], e["action"])


def test_translation_and_the_portuguese_menu_table(menus):
    text = (REPO / "installer").read_text(encoding="utf-8", errors="replace") if (REPO / "installer").exists() else ""
    table = mc.menu_pt(text)
    if text:
        assert table.get("Control Dashboard") == "Painel de Controle"
    t = mc.with_menu_pt(lambda s: "<" + s + ">", {"Control Dashboard": "Painel de Controle"})
    cat = mc.catalog(menus, t)
    assert cat[0]["label"] == "Painel de Controle"
    assert cat[1]["label"].startswith("<") or cat[1]["label"].endswith(">")
    assert mc.with_menu_pt(str, {})("x") == "x"


def test_split_icon():
    assert mc.split_icon("📦  Install Koha server") == ("📦", "Install Koha server")
    assert mc.split_icon("Control Dashboard") == ("", "Control Dashboard")
    assert mc.split_icon("Z39.50 servers") == ("", "Z39.50 servers")


def test_find_menus(tmp_path):
    assert mc.find_menus(tmp_path) is None
    target = tmp_path / "panel" / "kei_panel"
    target.mkdir(parents=True)
    (target / "menus.py").write_text("SECTIONS = ()\n")
    assert mc.find_menus(tmp_path) == target / "menus.py"
    assert mc.find_menus(tmp_path / "nothing", tmp_path) == target / "menus.py"


def test_panel_only(menus):
    assert "backup-download" in mc.panel_only(menus)
