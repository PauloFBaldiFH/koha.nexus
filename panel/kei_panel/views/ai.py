"""AIView: settings of the AI cataloguing tabs, plus a connection test.

The settings file is the one the staff interface's "AI settings" tab
writes (aiconf.py). The test lists the provider's models in a THREAD
worker (urllib blocks), behind the Pac-Man modal.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal
from textual.widgets import Button, Input, Label, Select

from .. import aiconf
from ..i18n import t
from ..tasks import Reporter, TaskResult, run_with_loader
from .base import SectionView


class AIView(SectionView):
    def conf_file(self) -> Path:
        if self.app.env.demo:
            return Path(tempfile.gettempdir()) / "kei-demo-vision.conf"
        return aiconf.conf_path(self.app.env.instance)

    def compose(self) -> ComposeResult:
        c = aiconf.load(self.conf_file())
        yield from self.heading()
        yield Label(t("Photos of a book's cover and title page become a MARC record draft in the staff interface."),
                    classes="view-prompt")
        with Grid(classes="form-grid"):
            yield Label(t("Provider"))
            yield Select([(p, p) for p in aiconf.PROVIDERS], value=c["provider"], allow_blank=False,
                         id="ai-provider")
            yield Label(t("Server URL"))
            yield Input(c["url"], id="ai-url")
            yield Label(t("Model"))
            yield Input(c["model"], id="ai-model")
            yield Label(t("API token"))
            yield Input(c["token"], password=True, id="ai-token",
                        placeholder=t("not needed for Ollama / LM Studio"))
        with Horizontal(classes="form-buttons"):
            yield Button(t("Save"), id="ai-save", variant="primary")
            yield Button(t("Test connection"), id="ai-test")

    def values(self) -> dict[str, str]:
        c = aiconf.load(self.conf_file())
        c["provider"] = str(self.query_one("#ai-provider", Select).value)
        for key in ("url", "model", "token"):
            c[key] = self.query_one(f"#ai-{key}", Input).value.strip()
        return aiconf.with_defaults(c)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "ai-provider" and event.value in aiconf.DEFAULTS:
            url, model = aiconf.DEFAULTS[event.value]
            self.query_one("#ai-url", Input).value = url
            self.query_one("#ai-model", Input).value = model

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ai-save":
            try:
                aiconf.save(self.conf_file(), self.values())
                self.app.notify(t("Saved."))
            except OSError as e:
                self.app.notify(str(e), severity="error")
        elif event.button.id == "ai-test":
            self.test_connection()

    def test_connection(self) -> None:
        conf = self.values()
        demo = self.app.env.demo

        def job(reporter: Reporter) -> list[str]:       # thread worker
            reporter.status(conf["url"])
            if demo:
                import time
                for i in range(10):
                    if reporter.cancelled:
                        return []
                    reporter.progress(i + 1, 10)
                    time.sleep(0.2)
                return [conf["model"] or "demo-model"]
            return aiconf.list_models(conf)

        run_with_loader(self.app, t("Testing the AI provider"), job, on_done=self._tested)

    def _tested(self, result: TaskResult) -> None:
        if result.ok:
            models = result.value or []
            self.app.notify(f"{t('Connected.')} {len(models)} {t('models')}", timeout=6)
        else:
            self.app.task_failed(t("Testing the AI provider"), result)
