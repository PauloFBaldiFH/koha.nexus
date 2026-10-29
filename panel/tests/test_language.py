import asyncio

from conftest import INSTALLER

from kei_panel.env import read_lang_conf
from kei_panel.screens.language import (ENGLISH_NAMES, RESTART_CODE, LanguageScreen, language_items,
                                       option_label, write_language)


def test_items_come_from_the_installer():
    items = dict(language_items(INSTALLER))
    assert items["pt-BR"] == "Português (Brasil)" and "en-GB" in items and len(items) >= 20


def test_write_keeps_other_lines(tmp_path):
    conf = tmp_path / "translation.conf"
    conf.write_text('KOHA_LANG="pt-BR"\nKOHA_PANEL_LANG="en"\n')
    write_language("es-ES", conf)
    assert read_lang_conf("KOHA_PANEL_LANG", conf) == "es"
    assert read_lang_conf("KOHA_PANEL_LANG_FULL", conf) == "es-ES"
    assert read_lang_conf("KOHA_LANG", conf) == "pt-BR"


def test_choosing_exits_for_a_restart(tmp_path):
    from textual.app import App

    conf = tmp_path / "translation.conf"

    class Host(App):
        def on_mount(self):
            self.push_screen(LanguageScreen(INSTALLER, conf))

    async def main():
        app = Host()
        async with app.run_test() as pilot:
            await pilot.pause(0.2)
            await pilot.press("down", "enter")     # the entry after pt-BR
        return app.return_code

    assert asyncio.run(main()) == RESTART_CODE
    assert read_lang_conf("KOHA_PANEL_LANG_FULL", conf) == "es-ES"


def test_classic_console_gets_english_names_first():
    items = dict(language_items(INSTALLER))
    assert set(ENGLISH_NAMES) <= set(items)
    assert option_label("ru-RU", items["ru-RU"], plain=True) == "Russian - Русский   (ru-RU)"
    assert option_label("ru-RU", items["ru-RU"]) == "Русский   (ru-RU)"
    assert option_label("pt-BR", items["pt-BR"], plain=True) == "Português (Brasil)   (pt-BR)"


def test_right_to_left_names_only_in_english_in_the_classic_console():
    items = dict(language_items(INSTALLER))
    assert option_label("ar-Arab", items["ar-Arab"], plain=True) == "Arabic   (ar-Arab)"
    assert option_label("fa-Arab", items["fa-Arab"], plain=True) == "Persian   (fa-Arab)"
    assert option_label("ar-Arab", items["ar-Arab"]) == f"{items['ar-Arab']}   (ar-Arab)"
