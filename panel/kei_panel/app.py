"""KohaPanelApp: the Textual panel."""

from __future__ import annotations

import os
import re
import traceback
from pathlib import Path
from typing import Callable

from textual.app import App
from textual.binding import Binding

from .bridge import Bridge, BridgeError
from .env import PanelEnv, log_error
from .i18n import Translator, install, t
from .menus import Entry
from .screens.dialogs import ConfirmScreen, ResultScreen
from .screens.main import MainScreen
from .tasks import TaskResult, run_with_loader, verb_job
from .theme import load_theme, save_theme


HIDDEN_SYSTEM_COMMANDS = {"Screenshot", "Maximize", "Minimize"}
# Colours and other terminal escapes (ANSI CSI and OSC) never go to the
# clipboard with a copied command.
_ESCAPES = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")


def clean_copy(text: str) -> str:
    return _ESCAPES.sub("", text or "").strip("\n")


class KohaPanelApp(App):
    CSS_PATH = Path(__file__).with_name("panel.tcss")
    TITLE = "koha.nexus"
    BINDINGS = [
        Binding("q", "quit", t("Exit")),
        Binding("question_mark", "help", "Help", show=False),
    ]

    def __init__(self, env: PanelEnv):
        install(Translator(env.lang, env.installer, env.plain))
        super().__init__()
        self.env = env
        self.bridge = Bridge(env)

    def _handle_exception(self, error: Exception) -> None:
        # Textual shows the traceback on the terminal after it exits; config.sh
        # then covers it with the classic panel, so it is kept in the log too.
        log_error("".join(traceback.format_exception(type(error), error, error.__traceback__)))
        super()._handle_exception(error)

    def copy_to_clipboard(self, text: str, quiet: bool = False) -> None:
        # Every copy ends here: Ctrl+C on text selected with the mouse, the
        # Copy buttons and the "c" key. Textual sends it as OSC 52, so the
        # terminal puts it on the clipboard of the computer the person is
        # at, also over SSH.
        super().copy_to_clipboard(clean_copy(text))
        if not quiet:
            self.notify(t("Copied."), timeout=3)

    def open_url(self, url: str, new_tab: bool = True) -> None:
        # Textual's own open_url uses the webbrowser module, which may start
        # a text browser over the panel on a server (opener.py). Where no
        # browser can be opened, the address is copied instead.
        from .opener import open_url
        if open_url(url):
            self.notify(t("Opening ${url} in the browser.", url=url), timeout=4)
        else:
            self.copy_to_clipboard(url, quiet=True)
            self.notify(t("No browser can be opened from here. Address copied: paste it in your browser."),
                        timeout=6)

    def get_system_commands(self, screen):
        # Textual's Screenshot and Maximize/Minimize do not work for the
        # panel (ROADMAP subject 1): they are left out of the command search.
        for command in super().get_system_commands(screen):
            if command.title not in HIDDEN_SYSTEM_COMMANDS:
                yield command

    def _signal_started(self) -> None:
        """The first screen is on the terminal: config.sh's start-up watchdog
        (KEI_PANEL_READY_FILE) stands down."""
        path = os.environ.get("KEI_PANEL_READY_FILE")
        if path:
            try:
                Path(path).touch()
            except OSError:
                pass

    def on_mount(self) -> None:
        self.call_after_refresh(self._signal_started)
        # Classic console / Linux console: ASCII borders (panel.tcss, App.-plain).
        self.set_class(self.env.plain, "-plain")
        self.theme = load_theme(self.available_themes)
        self.theme_changed_signal.subscribe(self, lambda theme: save_theme(theme.name))
        if not self.env.demo and not self.env.language_chosen():
            # New installation: the language first (config.sh restarts the app in it).
            from .screens.language import LanguageScreen
            self.push_screen(LanguageScreen(self.env.installer))
            return
        self.push_screen(MainScreen())
        if self.env.demo:
            self.notify("Demo mode: nothing is run on this machine.", timeout=4)

    def on_resize(self, event) -> None:
        # 80-column SSH sessions: two cards per row instead of three.
        self.set_class(event.size.width < 110, "-narrow")

    # ------------------------------------------------------------------
    # Running a menu entry: the one place that decides how
    # ------------------------------------------------------------------
    def runs_in_background(self, entry: Entry) -> bool:
        return entry.kind == "background" or bool(entry.verb and self.bridge.supports(entry.verb[0]))

    def is_native(self, entry: Entry) -> bool:
        """Ported to the panel's own screens, and the installer can run it."""
        from . import routines
        if not (entry.kind == "native" and routines.has(entry.action) and self.bridge.supports_tasks()):
            return False
        task = routines.task_of(entry.action)
        return not task or self.bridge.has_task(task)

    def run_native(self, action: str, after: Callable[[], None] | None = None) -> None:
        from . import routines

        async def flow() -> None:
            try:
                await routines.ROUTINES[action](self)
            finally:
                if after:
                    after()

        self.run_worker(flow(), group="routine", exclusive=True, exit_on_error=False)

    def run_entry(self, entry: Entry, after: Callable[[], None] | None = None) -> None:
        label = t(entry.label)
        if self.is_native(entry):
            self.run_native(entry.action, after)
            return
        if not self.runs_in_background(entry):
            try:
                rc = self.bridge.run_interactive(self, entry.action)
            except BridgeError as e:
                self.notify(str(e), severity="error")
                return
            if rc not in (0, None):
                self.notify(f"{label}: exit {rc}", severity="warning")
            if after:
                after()
            return

        def start(confirmed: bool | None = True) -> None:
            if not confirmed:
                return

            def done(result: TaskResult) -> None:
                if result.ok:
                    self.notify(f"{label}: {t('Done!')}", timeout=5)
                elif not result.cancelled:
                    self.task_failed(label, result)
                if after:
                    after()

            run_with_loader(self, label, verb_job(self.bridge, entry.verb), on_done=done)

        if entry.confirm:
            self.push_screen(ConfirmScreen(label, t(entry.confirm)), callback=start)
        else:
            start()

    def task_failed(self, title: str, result: TaskResult) -> None:
        if result.cancelled:
            self.notify(f"{title}: {t('Cancelled')}", severity="warning")
        else:
            self.push_screen(ResultScreen(title, result))
