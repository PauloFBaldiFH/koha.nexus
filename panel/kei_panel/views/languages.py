"""LanguagesView: the Language center (study 17.2).

One row for the panel and one for each system, with the language it uses
now and one button: the panel's own choice (only the panel), Koha's
routines, Tainacan's WordPress language, DSpace's interface languages. A
system that is not installed shows "Not installed" and no button. The
cards of before stay below the rows.

Opening the center only reads (languages.py); the values are read again
each time it is shown and after a routine ends.
"""

from __future__ import annotations

import json

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label

from .. import languages, platforms
from ..env import TRANSLATION_CONFIG
from ..i18n import t
from ..screens.language import language_items
from .base import SectionView

# The routines behind the buttons (Koha's is a choice of its cards).
ROUTINE = {"panel": "panel-language", "tainacan": "tainacan-language", "dspace": "dspace-languages"}
KOHA_ACTIONS = ("languages", "lang-download", "lang-activate", "lang-list")


class LanguagesView(SectionView):
    conf = TRANSLATION_CONFIG

    def compose(self) -> ComposeResult:
        yield from self.heading()
        with Vertical(id="lang-rows"):
            for key, title, _platform in languages.ROWS:
                with Horizontal(classes="lang-row", id=f"lang-{key}"):
                    yield Label(t(title), classes="lang-name")
                    with Vertical(classes="lang-text"):
                        yield Label("…", classes="lang-value", markup=False)
                        yield Label("", classes="lang-note", markup=False)
                    yield Button(t(languages.BUTTONS[key]), id=f"lang-{key}-button", classes="small", compact=True)
        yield from self.cards()

    def on_mount(self) -> None:
        # Read as soon as it exists too: a Show event can be missed when the
        # view is mounted and made current in one step on a busy machine.
        self.refresh_data()

    def on_show(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        self.run_worker(self.read(), group="languages", exclusive=True, exit_on_error=False)

    def show_row(self, key: str, row: languages.Row) -> None:
        box = self.query_one(f"#lang-{key}", Horizontal)
        box.query_one(".lang-value", Label).update(row.value)
        box.query_one(".lang-note", Label).update(row.note)
        button = box.query_one(Button)
        button.display = row.button
        box.set_class(not row.button, "-absent")

    async def read(self) -> None:
        app = self.app
        self.show_row("panel", languages.panel_row(
            languages.panel_code(self.conf, app.env.lang), language_items(app.env.installer)))
        bridge = app.bridge
        if not app.platform_ready("koha"):
            self.show_row("koha", languages.absent_row())
        else:
            out = None
            if bridge.has_task("koha-languages"):
                try:
                    out = await bridge.task("koha-languages")
                except Exception:  # noqa: BLE001 - the row then says it was not read
                    out = None
            self.show_row("koha", languages.koha_row(out))
        if not app.platform_ready("tainacan"):
            self.show_row("tainacan", languages.absent_row())
        else:
            try:
                status = await bridge.status()
            except Exception:  # noqa: BLE001
                status = {}
            state = platforms.tainacan_from_status(status if isinstance(status, dict) else {})
            self.show_row("tainacan", languages.tainacan_row(state.lang or state.check("lang")))
        if not app.platform_ready("dspace"):
            self.show_row("dspace", languages.absent_row())
        else:
            data = None
            if bridge.has_task("dspace-panel"):
                from ..dspace import payload
                env = {"KEI_DSPACE_OPERATIONS_DATA": json.dumps({"panel_language": app.env.lang})}
                try:
                    out = await bridge.task("dspace-panel", "operations", "languages", env=env)
                    data = payload(out) if out.ok else None
                except Exception:  # noqa: BLE001
                    data = None
            self.show_row("dspace", languages.dspace_row(data))

    @on(Button.Pressed, ".lang-row Button")
    def _pressed(self, event: Button.Pressed) -> None:
        event.stop()
        key = (event.button.id or "").removeprefix("lang-").removesuffix("-button")
        if key == "koha":
            self.choose_koha()
        elif key in ROUTINE:
            self.app.run_native(ROUTINE[key], after=self.refresh_data)

    def choose_koha(self) -> None:
        """Koha's routines, as its cards below (each one asks its own questions)."""
        from ..screens.dialogs import ChoiceScreen
        entries = {e.action: e for e in self.section.entries if e.action in KOHA_ACTIONS}
        options = [(a, t(entries[a].label)) for a in KOHA_ACTIONS if a in entries]

        def chosen(action: str | None) -> None:
            if action in entries:
                self.app.run_entry(entries[action], after=self.refresh_data)

        self.app.push_screen(ChoiceScreen(t("Koha languages"), t(
            "Koha's language packs and the active language of the OPAC and the staff interface. "
            "\"Download & activate\" also changes this panel when it has that language."), options),
            callback=chosen)
