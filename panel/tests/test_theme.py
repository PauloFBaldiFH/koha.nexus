"""Theme: Flexoki by default, the person's choice kept for the next start,
and a command search whose chosen line stands out (ROADMAP subject 1)."""

import asyncio

import pytest

from kei_panel import theme
from kei_panel.app import KohaPanelApp
from kei_panel.env import PanelEnv


@pytest.fixture
def theme_file(tmp_path, monkeypatch):
    path = tmp_path / "panel-theme.conf"
    monkeypatch.setenv("KEI_PANEL_THEME_FILE", str(path))
    return path


def start(change_to=None):
    async def main():
        app = KohaPanelApp(PanelEnv(installer=None, lang="en", plain=False, demo=True))
        async with app.run_test() as pilot:
            await pilot.pause(0.2)
            first = app.theme
            if change_to:
                app.theme = change_to
                await pilot.pause(0.2)
            return first
    return asyncio.run(main())


def test_flexoki_is_the_default(theme_file):
    assert start() == "flexoki"


def test_the_chosen_theme_comes_back(theme_file):
    start(change_to="nord")
    assert theme_file.read_text().strip() == "nord"
    assert start() == "nord"


def test_unknown_or_unreadable_names_give_the_default(theme_file):
    theme_file.write_text("no-such-theme\n")
    assert theme.load_theme(["flexoki", "nord"]) == "flexoki"
    theme_file.write_bytes(b"\xff\xfe")
    assert theme.load_theme(["flexoki", "nord"]) == "flexoki"


def test_a_file_that_cannot_be_written_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv("KEI_PANEL_THEME_FILE", str(tmp_path / "missing-dir" / "panel-theme.conf"))
    theme.save_theme("nord")
    assert not (tmp_path / "missing-dir").exists()


def test_command_search_lines_stand_out(theme_file):
    from textual.command import CommandList

    async def main():
        app = KohaPanelApp(PanelEnv(installer=None, lang="en", plain=False, demo=True))
        async with app.run_test() as pilot:
            await pilot.pause(0.2)
            await pilot.press("ctrl+p")
            await pilot.pause(0.3)
            lst = app.screen.query_one(CommandList)
            hi = lst.get_component_styles("option-list--option-highlighted")
            hover = lst.get_component_styles("option-list--option-hover")
            primary = app.current_theme.to_color_system().primary
            return hi.background, hover.background, primary
    hi, hover, primary = asyncio.run(main())
    assert hi.rgb == primary.rgb and hover.a > 0.3
