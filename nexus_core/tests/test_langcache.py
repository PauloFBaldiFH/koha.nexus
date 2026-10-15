import base64
from pathlib import Path

import pytest

from nexus_core.langcache import Translator, language_code, read_cache

REPO = Path(__file__).resolve().parents[2]


def line(en, tr):
    return base64.b64encode(en.encode()).decode() + "|" + base64.b64encode(tr.encode()).decode()


@pytest.mark.parametrize("culture, code", [
    ("pt-BR", "pt"), ("es_ES", "es"), ("fil-PH", "tl"), ("nb-NO", "no"), ("nn", "no"), ("", "en"), ("EN-us", "en"),
])
def test_language_code(culture, code):
    assert language_code(culture) == code


def test_read_cache_skips_comments_bad_lines_and_empty_translations(tmp_path):
    f = tmp_path / "pt.cache"
    f.write_text("\n".join([
        "# koha-easy-installer lang 1.5.56",
        line("Koha is running", "O Koha est\u00e1 em execu\u00e7\u00e3o"),
        line("Empty", "   "),
        "not|base64!|x",
        "@@@|###",
        "",
    ]), encoding="utf-8")
    assert read_cache(f) == {"Koha is running": "O Koha est\u00e1 em execu\u00e7\u00e3o"}
    assert read_cache(tmp_path / "missing.cache") == {}


def test_translator_keeps_english_when_placeholders_differ():
    t = Translator({"Attention: {0} is offline": "Aten\u00e7\u00e3o: {0} est\u00e1 fora do ar",
                    "Answers (HTTP {0})": "Responde (HTTP)"})
    assert t("Attention: {0} is offline").format("MariaDB") == "Aten\u00e7\u00e3o: MariaDB est\u00e1 fora do ar"
    assert t("Answers (HTTP {0})") == "Answers (HTTP {0})"
    assert t("Not in the dictionary") == "Not in the dictionary"


def test_translator_shows_the_real_koha_folder():
    assert Translator(root="C:\\Koha")("The log is in C:\\KohaEasy\\logs.") == "The log is in C:\\Koha\\logs."
    assert Translator(root="C:\\KohaEasy")("C:\\KohaEasy") == "C:\\KohaEasy"


def test_the_portuguese_dictionary_of_this_repository_loads():
    t = Translator.load(REPO / "lang", "pt-BR")
    assert t.code == "pt"
    assert t("All services are running") == "Todos os servi\u00e7os est\u00e3o operacionais"
    assert Translator.load(REPO / "lang", "en-US")("All services are running") == "All services are running"
