import base64

from conftest import INSTALLER

from kei_panel.env import normalize_panel_language
from kei_panel.i18n import Translator, expand, is_safe, load_cache, load_menu_pt


def b64(s):
    return base64.b64encode(s.encode()).decode()


def test_menu_pt_is_read_from_the_installer():
    table = load_menu_pt(INSTALLER)
    assert table["Control Dashboard"] == "Painel de Controle"
    assert table["💾  Backup center"].startswith("💾")


def test_portuguese_prefers_menu_pt():
    t = Translator("pt", INSTALLER)
    assert t("Control Dashboard") == "Painel de Controle"
    assert t("Back") == "Voltar"


def test_cache_entries_and_safety(tmp_path):
    f = tmp_path / "xx.cache"
    f.write_text("# header\n"
                 f"{b64('Hello ${name}')}|{b64('Olá ${name}')}\n"
                 f"{b64('Bad ${a}')}|{b64('Ruim ${b}')}\n"
                 "not|base64!\n")
    table = load_cache(f)
    assert table["Hello ${name}"] == "Olá ${name}"
    assert not is_safe("Bad ${a}", table["Bad ${a}"])
    assert expand("Olá ${name}", {"name": "Ana"}) == "Olá Ana"
    assert expand("${x:-default}", {}) == "default"


def test_plain_mode_strips_icons():
    t = Translator("en", INSTALLER, plain=True)
    assert t("💾  Backup center") == "Backup center"


def test_language_codes():
    assert normalize_panel_language("pt-BR") == "pt"
    assert normalize_panel_language("fil") == "tl"
    assert normalize_panel_language("") == "pt"
    assert normalize_panel_language("es-ES") == "es"
