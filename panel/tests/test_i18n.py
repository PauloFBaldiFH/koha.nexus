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


def test_portuguese_covers_literal_panel_messages():
    """New literal messages must ship with a usable bundled translation."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    table = load_cache(root / 'lang/pt.cache')
    table.update(load_menu_pt(root / 'installer'))
    missing = []
    unsafe = []
    for path in sorted((root / 'panel/kei_panel').rglob('*.py')):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name) and node.func.id == 't'
                    and node.args and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                continue
            source = node.args[0].value
            if not source:
                continue
            location = f'{path.relative_to(root)}:{node.lineno}: {source!r}'
            if source not in table:
                missing.append(location)
            elif not is_safe(source, table[source]):
                unsafe.append(location)
    assert not missing, 'Missing Portuguese entries:\n' + '\n'.join(missing)
    assert not unsafe, 'Unsafe Portuguese placeholders:\n' + '\n'.join(unsafe)
