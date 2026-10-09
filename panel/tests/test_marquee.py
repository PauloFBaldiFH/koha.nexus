"""The scrolling hint line of the action cards (widgets/marquee.py)."""

import asyncio

from rich.cells import cell_len
from textual.app import App
from textual.containers import Vertical
from textual.widgets import Button

from kei_panel.widgets import marquee
from kei_panel.widgets.marquee import Marquee, cell_head, cell_window


def test_cell_window_is_always_the_width():
    assert cell_window("abcdef", 0, 3) == "abc"
    assert cell_window("abcdef", 4, 3) == "ef "
    assert cell_window("ab", 0, 5) == "ab   "
    # A wide character cut by either edge becomes a space, never half a glyph.
    assert cell_window("a界b", 2, 3) == " b "
    assert cell_window("ab界", 0, 3) == "ab "
    for start in range(8):
        assert cell_len(cell_window("中文字幕很长", start, 5)) == 5


def test_cell_head_marks_the_cut():
    assert cell_head("Opens the classic screens", 10) == "Opens the…"
    assert cell_len(cell_head("中文字幕很长", 5)) <= 5


class _Card(Vertical, can_focus=True):
    DEFAULT_CSS = "_Card { width: 14; height: 3; }"

    def compose(self):
        yield Marquee(self.id == "long" and "Opens the classic screens" or "Fits")

    def on_focus(self):
        self.query_one(Marquee).run(True)

    def on_blur(self):
        self.query_one(Marquee).run(False)


class _App(App):
    def compose(self):
        yield _Card(id="long")
        yield _Card(id="short")
        yield Button("other")


def test_long_text_scrolls_only_while_focused(monkeypatch):
    monkeypatch.setattr(marquee, "STEP", 0.01)
    monkeypatch.setattr(marquee, "HOLD", 2)

    async def main():
        app = _App()
        async with app.run_test(size=(40, 10)) as pilot:
            long, short = app.query(Marquee)
            app.query_one(Button).focus()
            await pilot.pause(0.05)
            assert str(short.render()) == "Fits" and not short.overflow
            assert str(long.render()).endswith("…")
            assert long.overflow > 0

            app.query_one("#short").focus()
            await pilot.pause(0.1)
            assert short._ticker is None              # text that fits: no timer at all

            app.query_one("#long").focus()
            seen = set()
            for _ in range(80):
                await pilot.pause(0.01)
                seen.add(long._shift)
                assert cell_len(str(long.render())) == long.content_size.width
            assert 0 in seen and long.overflow in seen   # reached the end and came back

            app.query_one(Button).focus()
            await pilot.pause(0.05)
            assert not long._scrolling and long._shift == 0 and str(long.render()).endswith("…")

    asyncio.run(main())


def test_hovering_an_action_card_runs_its_hint():

    from conftest import INSTALLER
    from kei_panel.app import KohaPanelApp
    from kei_panel.env import PanelEnv
    from kei_panel.widgets.cards import ActionCard

    async def main():
        app = KohaPanelApp(PanelEnv(installer=INSTALLER, lang="en", plain=False, demo=True))
        async with app.run_test(size=(80, 40)) as pilot:
            await pilot.pause(0.3)
            app.screen.action_show("security")
            await pilot.pause(0.3)
            card = next(c for c in app.screen.query(ActionCard) if c.entry.action == "vpn")
            hint = card.query_one(Marquee)
            assert hint.region.right <= card.region.right - 1    # inside the border
            app.screen.query_one("#sidebar").focus()
            hint.set_text("A hint much longer than any card on an eighty column terminal")
            await pilot.pause(0.05)
            assert hint.overflow > 0 and not hint._scrolling
            await pilot.hover(card)
            await pilot.pause(0.05)
            running_on_hover = hint._scrolling
            await pilot.hover("#sidebar")
            await pilot.pause(0.05)
            return running_on_hover, hint._scrolling

    assert asyncio.run(main()) == (True, False)
