import base64

import pytest

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
    source = "Compressing captured backup (${codec}); WordPress has resumed."
    assert t.menu_pt[source] == "Compactando o backup capturado (${codec}); o WordPress voltou a funcionar."
    assert t(source, codec="XZ") == "Compactando o backup capturado (XZ); o WordPress voltou a funcionar."


@pytest.mark.parametrize("language, exit_label", [("pt", "Sair"), ("ar", "خروج")])
def test_main_footer_translates_bindings_after_install(language, exit_label):
    import asyncio

    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv
    from kei_panel.glyphs import split_icon
    from kei_panel.menus import section

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang=language, plain=False, demo=True))
        translator = Translator(language, INSTALLER)
        async with app.run_test(size=(100, 30)):
            bindings = app.screen.active_bindings
            assert bindings["d"].binding.description == split_icon(translator(section("dashboard").label))[1]
            assert bindings["q"].binding.description == exit_label

    asyncio.run(main())


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


def test_european_panel_translation_coverage():
    """Cover messages, menu metadata and known dynamically translated labels.

    Literal t() calls alone miss section names, card descriptions and status
    tables. Portuguese is also used to recognize existing translated labels
    stored in constants; arbitrary paths and protocol values are not translated.
    """
    import ast
    from pathlib import Path
    from kei_panel import menus

    root = Path(__file__).resolve().parents[2]
    portuguese = load_cache(root / 'lang/pt.cache')
    messages = set()
    for path in (root / 'panel/kei_panel').rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 't' and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                messages.add(node.args[0].value)
            elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
                  and node.value in portuguese):
                messages.add(node.value)
    for section in menus.SECTIONS:
        messages.update((section.label, section.title, section.prompt))
        for entry in section.entries:
            messages.update((entry.label, entry.confirm))
    messages.update(menus.DESCRIPTIONS.values())
    messages.discard('')
    for language in ('es', 'fr', 'de', 'it'):
        table = load_cache(root / f'lang/{language}.cache')
        missing = sorted(messages - table.keys())
        unsafe = sorted(key for key in messages & table.keys()
                        if not is_safe(key, table[key]))
        assert not missing, f'{language}: missing translations: {missing}'
        assert not unsafe, f'{language}: invalid placeholders: {unsafe}'


def test_bundled_cache_lines_are_readable():
    """Reject malformed cache entries instead of silently falling back to English."""
    import base64
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    for path in sorted((root / 'lang').glob('*.cache')):
        for number, line in enumerate(path.read_text(encoding='ascii').splitlines(), 1):
            if not line or line.startswith('#'):
                continue
            key, separator, value = line.partition('|')
            assert separator, f'{path.name}:{number}: missing cache separator'
            try:
                source = base64.b64decode(key, validate=True).decode('utf-8')
                translated = base64.b64decode(value, validate=True).decode('utf-8')
            except (ValueError, UnicodeError) as exc:
                raise AssertionError(f'{path.name}:{number}: invalid cache entry') from exc
            assert source and translated, f'{path.name}:{number}: empty cache entry'
            assert is_safe(source, translated), f'{path.name}:{number}: invalid placeholders'


def test_tainacan_diagnosis_translates_states_and_preserves_technical_values(monkeypatch):
    from kei_panel import i18n
    from kei_panel.routines.platforms import tainacan_diagnosis_value

    translator = Translator("pt", INSTALLER)
    monkeypatch.setattr(i18n, "_current", translator)
    assert tainacan_diagnosis_value("db", "exited") == translator("Stopped") != "exited"
    assert tainacan_diagnosis_value("images_pinned", "yes") == "Sim"
    assert tainacan_diagnosis_value("audit", "network=tainacan") == "network=tainacan"


def test_dspace_protocol_localizes_messages_without_expanding_raw_values(monkeypatch):
    from kei_panel import i18n
    from kei_panel.bridge import TaskOutcome

    monkeypatch.setattr(i18n, "_current", Translator("pt", INSTALLER))
    outcome = TaskOutcome()
    outcome.feed("@@msg error DSpace\tAnother DSpace operation is running.", translate_messages=True)
    assert outcome.last("error")[2] == "Outra operação do DSpace está sendo executada."
    outcome.feed("@@msg error DSpace\tUnexpected path /var/${literal}", translate_messages=True)
    assert outcome.last("error")[2] == "Unexpected path /var/${literal}"
