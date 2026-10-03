"""AIView (Module 1): AI provider setup for the cataloguing tools.

  ┌ AI provider ─┐ ┌ Google Gemini ───────────────────────────┐
  │ ( ) Ollama   │ │ Server URL  [..........................] │
  │ (•) Gemini   │ │ Model       [gemini-2.5-flash..........] │
  │ ( ) OpenAI   │ │ API key     [••••••••••••••••••••••••••] │
  │ ( ) Claude   │ │ saved key ••••a1b2 · get one at ...      │
  │ ( ) Other    │ └──────────────────────────────────────────┘
  └──────────────┘  [Test connection] [Save]
  [Provider]  [Connection]  [MARC Replace]       status cards
  ┌ Next: MARC Replace ─────────────────────────────────────┐
  │ ready: photos become a MARC draft  [Open MARC Replace]   │
  └──────────────────────────────────────────────────────────┘

Local Ollama gets its own box: is it running, is the model there,
download it. Everything that touches the network (connection test, Ollama
check, model download) is a thread job behind the Pac-Man loader
(run_with_loader), so the screen never freezes.

Keys: typed in a password field, saved to vision.conf / ai-keys.conf with
mode 0600 (aiconf), never put back in a widget or a message: the field
stays empty and shows the saved key masked; empty means "keep it".
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.widgets import Button, Input, Label, RadioButton, RadioSet

from .. import aiclient, aiconf, marcreplace
from ..i18n import t
from ..tasks import Reporter, TaskFailed, TaskResult, run_with_loader
from ..widgets.cards import StatusCard
from .base import SectionView


class AIView(SectionView):
    BINDINGS = [
        Binding("ctrl+s", "save", t("Save")),
        Binding("f5", "test", t("Test connection")),
    ]

    def __init__(self, section):
        super().__init__(section)
        self.provider = "openai"
        self.check: aiclient.Check | None = None
        self.check_error = ""

    # ------------------------------------------------------------------
    # Files
    # ------------------------------------------------------------------
    def conf_file(self) -> Path:
        if self.app.env.demo:
            return Path(tempfile.gettempdir()) / "kei-demo-ai" / "vision.conf"
        return aiconf.conf_path(self.app.env.instance)

    def saved(self) -> dict[str, str]:
        return aiconf.load(self.conf_file())

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        c = self.saved()
        self.provider = c["provider"]
        yield from self.heading()
        yield Label(t("Choose the AI that reads the photos of a book's cover and title page and drafts "
                      "its MARC record in the staff interface."), classes="view-prompt")
        with Horizontal(id="ai-body"):
            with RadioSet(id="ai-providers"):
                for p in aiconf.SELECTOR_ORDER:
                    yield RadioButton(t(aiconf.LABELS[p]), value=p == self.provider, id=f"ai-p-{p}")
            with Vertical(id="ai-details"):
                with Vertical(id="ai-form", classes="ai-box"):
                    with Grid(classes="form-grid"):
                        yield Label(t("Server URL"))
                        yield Input(c["url"], id="ai-url")
                        yield Label(t("Model"))
                        yield Input(c["model"], id="ai-model")
                        yield Label(t("API key"), id="ai-token-label")
                        yield Input("", password=True, id="ai-token")
                    yield Label("", id="ai-key-note", classes="ai-note")
                with Vertical(id="ai-ollama", classes="ai-box"):
                    yield Label(t("Not checked yet."), id="ai-ollama-state")
                    yield Label(t("Not installed? On this server run:") + f"\n  {aiclient.OLLAMA_INSTALL}\n"
                                + t("then choose a vision model (qwen2.5vl, llama3.2-vision, gemma3) and download it."),
                                id="ai-ollama-hint", classes="ai-note")
                    with Horizontal(classes="form-buttons"):
                        yield Button(t("Check Ollama"), id="ai-ollama-check")
                        yield Button(t("Download the model"), id="ai-ollama-pull")
                with Horizontal(classes="form-buttons"):
                    yield Button(t("Test connection"), id="ai-test", variant="primary")
                    yield Button(t("Save"), id="ai-save", variant="success")
        with Grid(classes="status-grid", id="ai-cards"):
            yield StatusCard(t("Provider"), id="card-ai-provider")
            yield StatusCard(t("Connection"), id="card-ai-connection")
            yield StatusCard(t("MARC Replace"), id="card-ai-marc")
        with Horizontal(id="ai-hook", classes="ai-box"):
            yield Label("", id="ai-hook-text")
            yield Button(t("Open MARC Replace"), id="ai-marc", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#ai-form").border_title = t(aiconf.LABELS[self.provider])
        self.query_one("#ai-ollama").border_title = t("Ollama on this server")
        self.query_one("#ai-hook").border_title = t("Next step: MARC Replace")
        self.apply_provider(self.provider, keep_fields=True)
        self.refresh_cards()

    # ------------------------------------------------------------------
    # Provider
    # ------------------------------------------------------------------
    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        event.stop()
        provider = (event.pressed.id or "").removeprefix("ai-p-")
        if provider in aiconf.PROVIDERS and provider != self.provider:
            self.apply_provider(provider)

    def apply_provider(self, provider: str, keep_fields: bool = False) -> None:
        self.provider = provider
        self.check, self.check_error = None, ""
        saved = self.saved()
        if not keep_fields:
            if saved["provider"] == provider:
                url, model = saved["url"], saved["model"]
            else:
                url, model = aiconf.DEFAULTS[provider]
            self.query_one("#ai-url", Input).value = url
            self.query_one("#ai-model", Input).value = model
            self.query_one("#ai-token", Input).value = ""
        self.query_one("#ai-form").border_title = t(aiconf.LABELS[provider])
        local = provider == "ollama"
        self.query_one("#ai-ollama").display = local
        for w in ("#ai-token-label", "#ai-token"):
            self.query_one(w).display = not local
        self.show_key_note()
        self.refresh_cards()

    def saved_key(self) -> str:
        return aiconf.key_for(self.conf_file(), self.provider)

    def show_key_note(self) -> None:
        token_input = self.query_one("#ai-token", Input)
        masked = aiconf.mask(self.saved_key())
        token_input.placeholder = (t("saved key ${key}: leave empty to keep it", key=masked)
                                   if masked else t("paste the API key here"))
        parts = []
        if masked:
            parts.append(t("Saved key:") + f" {masked}")
        help_ = aiconf.KEY_HELP.get(self.provider, "")
        if help_ and self.provider != "ollama":
            parts.append(t("Get a key at:") + f" {help_}" if help_.startswith("http") else help_)
        if self.provider == "ollama":
            parts.append(t("Runs on this server: no key, nothing leaves the machine."))
        self.query_one("#ai-key-note", Label).update(" · ".join(parts))

    def values(self) -> dict[str, str]:
        """The settings as typed; an empty key field keeps the saved key."""
        c = self.saved()
        c["provider"] = self.provider
        c["url"] = self.query_one("#ai-url", Input).value.strip()
        c["model"] = self.query_one("#ai-model", Input).value.strip()
        typed = self.query_one("#ai-token", Input).value.strip()
        c["token"] = "" if self.provider == "ollama" else (typed or self.saved_key())
        return aiconf.with_defaults(c)

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {
            "ai-save": self.action_save,
            "ai-test": self.action_test,
            "ai-ollama-check": self.check_ollama,
            "ai-ollama-pull": self.pull_model,
            "ai-marc": self.open_marc_replace,
        }
        if event.button.id in actions:
            event.stop()
            actions[event.button.id]()

    def action_save(self) -> None:
        c = self.values()
        problem = aiconf.endpoint_problem(c)
        if problem:
            self.app.notify(t(aiconf.PROBLEMS[problem]), severity="error")
            return
        try:
            aiconf.save_all(self.conf_file(), c)
        except OSError as e:
            self.app.notify(str(e), severity="error")
            return
        self.query_one("#ai-token", Input).value = ""
        self.show_key_note()
        tested = self.check is not None
        self.app.notify(t("Saved.") + ("" if tested else " " + t("Test the connection to be sure it works.")))
        self.refresh_cards()

    # ------------------------------------------------------------------
    # Heavy work: always a thread job behind the Pac-Man loader
    # ------------------------------------------------------------------
    def action_test(self) -> None:
        conf = self.values()
        demo = self.app.env.demo

        def job(reporter: Reporter) -> aiclient.Check:       # thread worker
            reporter.status(conf["url"])
            if demo:
                problem = aiconf.endpoint_problem(conf)
                if problem:
                    raise TaskFailed(t(aiconf.PROBLEMS[problem]))
                _demo_wait(reporter, 1.5)
                return aiclient.Check(aiclient.models_endpoint(conf)[0], [conf["model"] or "demo"], True)
            try:
                return aiclient.check_connection(conf)
            except RuntimeError as e:
                raise TaskFailed(str(e)) from None

        run_with_loader(self.app, t("Testing the AI provider"), job, on_done=self._tested)

    def _tested(self, result: TaskResult) -> None:
        if result.ok:
            self.check, self.check_error = result.value, ""
            msg = f"{t('Connected.')} {len(self.check.models)} {t('models')}"
            if not self.check.found:
                msg += " · " + t("the model ${model} is not among them", model=self.values()["model"])
            self.app.notify(msg, severity="information" if self.check.found else "warning", timeout=6)
        elif not result.cancelled:
            self.check, self.check_error = None, result.error
            self.app.task_failed(t("Testing the AI provider"), result)
        self.refresh_cards()

    def check_ollama(self) -> None:
        conf = self.values()
        demo = self.app.env.demo

        def job(reporter: Reporter) -> tuple[str, aiclient.Check]:
            reporter.status(conf["url"])
            if demo:
                _demo_wait(reporter, 1.2)
                return "0.12-demo", aiclient.Check(conf["url"], ["llama3.2:latest"], False)
            try:
                version = aiclient.ollama_version(conf["url"])
                reporter.progress(1, 2)
                return version, aiclient.check_connection(conf)
            except RuntimeError as e:
                raise TaskFailed(str(e)) from None

        run_with_loader(self.app, t("Checking the local Ollama"), job, on_done=self._ollama_checked)

    def _ollama_checked(self, result: TaskResult) -> None:
        state = self.query_one("#ai-ollama-state", Label)
        if result.cancelled:
            return
        if not result.ok:
            state.update(t("Ollama is not answering at ${url}.", url=self.values()["url"]))
            self.check, self.check_error = None, result.error
            self.refresh_cards()
            return
        version, check = result.value
        self.check, self.check_error = check, ""
        model = self.values()["model"]
        have = t("installed") if check.found else t("not downloaded yet")
        state.update(f"Ollama {version} · {len(check.models)} {t('models')} · {model}: {have}")
        self.refresh_cards()

    def pull_model(self) -> None:
        conf = self.values()
        demo = self.app.env.demo

        def job(reporter: Reporter) -> str:
            reporter.status(t("Downloading ${model}", model=conf["model"]))
            if demo:
                _demo_wait(reporter, 3.0)
                return conf["model"]
            last = [""]

            def progress(status: str, done: int, total: int) -> None:
                if status != last[0]:
                    reporter.log(status)
                    reporter.status(status[:60])
                    last[0] = status
                if total:
                    reporter.progress(done, total)
            try:
                aiclient.ollama_pull(conf["url"], conf["model"], progress, lambda: reporter.cancelled)
            except RuntimeError as e:
                raise TaskFailed(str(e)) from None
            return conf["model"]

        run_with_loader(self.app, t("Downloading the model into Ollama"), job, on_done=self._pulled)

    def _pulled(self, result: TaskResult) -> None:
        if result.ok:
            self.app.notify(f"{result.value}: {t('Done!')}", timeout=5)
            self.check_ollama()
        else:
            self.app.task_failed(t("Downloading the model into Ollama"), result)

    # ------------------------------------------------------------------
    # MARC Replace hook
    # ------------------------------------------------------------------
    def ready(self) -> bool:
        """Set up = saved settings the staff interface can use."""
        return not aiconf.endpoint_problem(self.saved())

    def open_marc_replace(self) -> None:
        if not self.ready():
            self.app.notify(t("Set up and save an AI provider first."), severity="warning")
            return
        self.app.run_entry(_marc_entry(self.app.bridge), after=self.refresh_cards)

    def refresh_cards(self) -> None:
        saved = self.saved()
        ready = self.ready()
        name = t(aiconf.LABELS[saved["provider"]])
        self.query_one("#card-ai-provider", StatusCard).set(
            name if ready else t("Not set up"), saved["model"] if ready else t("Save a provider below"),
            "ok" if ready else "warn")

        conn = self.query_one("#card-ai-connection", StatusCard)
        if self.check and self.check.found:
            conn.set(t("Connected"), f"{len(self.check.models)} {t('models')}", "ok")
        elif self.check:
            conn.set(t("Connected"), t("model not found"), "warn")
        elif self.check_error:
            conn.set(t("Failed"), self.check_error[:60], "bad")
        else:
            conn.set(t("Not tested"), t("F5 tests it"))

        installed = marcreplace.installed(self.app.env.demo)
        self.query_one("#card-ai-marc", StatusCard).set(
            t("Installed") if installed else t("Not installed."), "marc_replace.pl",
            "ok" if installed else "warn")

        text = self.query_one("#ai-hook-text", Label)
        button = self.query_one("#ai-marc", Button)
        button.disabled = not ready
        if not ready:
            text.update(t("Set up and save an AI provider first: MARC Replace uses it to turn photos "
                          "into a MARC record draft."))
        elif installed:
            text.update(t("Ready: in the staff interface, MARC Replace > AI cataloguing (${url}) uses ${name}.",
                          url=marcreplace.VISION_URL, name=name))
            button.label = t("Open MARC Replace")
        else:
            text.update(t("Ready. Install the MARC Replace page to use ${name} from the staff interface.",
                          name=name))
            button.label = t("Install MARC Replace")


def _marc_entry(bridge):
    from ..menus import Entry
    # Native: its menus are panel screens (an installer without tasks keeps
    # the classic routine, see app.is_native).
    return Entry("🔀  Replace a MARC record (staff tool)", marcreplace.action(bridge), kind="native")


def _demo_wait(reporter: Reporter, seconds: float) -> None:
    steps = 12
    for i in range(steps):
        if reporter.cancelled:
            return
        reporter.progress(i + 1, steps)
        time.sleep(seconds / steps)
