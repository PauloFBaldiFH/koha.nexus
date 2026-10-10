"""AIView: both AI tools on one screen, MARC Replace (Module 1, AI
cataloguing) and the AI assistant of the staff home page (Module 2). They
share one provider; each may have its own model.

  ┌ AI provider ─┐ ┌ Local Ollama ────────────────────────────┐
  │ (•) Ollama   │ │ Server URL      [http://127.0.0.1:11434] │
  │ ( ) Gemini   │ │ Vision model    [qwen2.5vl:7b..........] │
  │ ( ) OpenAI   │ │ Chat model      [qwen2.5:3b............] │
  │ ( ) Claude   │ │ Models [Free / Accessible ...         v] │
  │ ( ) Other    │ │ [Load models] [Use for cataloguing] [chat]│
  └──────────────┘ └──────────────────────────────────────────┘
                    [Test connection] [Save]
                   ┌ Ollama on this server ───────────────────┐
                   │ Ollama 0.12 · 3 models · ...             │
                   │ Model [qwen2.5:3b · Balanced (CPU)    v] │
                   │ [Check] [Install] [Download] [Use for…]  │
                   └──────────────────────────────────────────┘
  [Provider]  [Connection]  [MARC Replace]  [AI assistant]   status cards
  ┌ The AI tools ───────────────────────────────────────────┐
  │ MARC Replace: ready ...               [Open MARC Replace]│
  │ AI assistant: installed ...  [Install, update or remove] │
  └──────────────────────────────────────────────────────────┘

Models: the list under the fields comes from the provider itself (Load
models, or a passed connection test) with the key typed or saved, in two
groups, Free / Accessible and Advanced (💳, needs a paid key or billing);
until it can be read, a built-in list is shown and says so (aimodels).

The Ollama box is always there and needs only Ollama itself: a model can be
downloaded whatever the provider and whether or not the assistant is
installed. Everything that touches the network (connection test, Ollama
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
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Select

from .. import aiclient, aiconf, aimodels, marcreplace
from ..i18n import t
from ..tasks import Reporter, TaskFailed, TaskResult, run_with_loader
from ..widgets.cards import StatusCard
from .base import SectionView

# The preset list's first choice: the models typed in the fields.
FIELDS = "@fields"
# Group headers of the model list: choosing one picks nothing.
HEADERS = ("@free", "@paid")


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
        self.ollama_models: list[str] = []
        self.discovery: aimodels.Discovery | None = None

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
        yield Label(t("Both AI tools in one place: MARC Replace reads the photos of a book's cover and title "
                      "page and drafts its MARC record, and the AI assistant answers librarians on the home page "
                      "of the staff interface. They use the AI provider below; each can have its own model."),
                    classes="view-prompt")
        with Horizontal(id="ai-body"):
            with RadioSet(id="ai-providers"):
                for p in aiconf.SELECTOR_ORDER:
                    yield RadioButton(t(aiconf.LABELS[p]), value=p == self.provider, id=f"ai-p-{p}")
            with Vertical(id="ai-details"):
                with Vertical(id="ai-form", classes="ai-box"):
                    with Horizontal(classes="form-row"):
                        yield Label(t("Server URL"), classes="form-label")
                        yield Input(c["url"], id="ai-url")
                    with Horizontal(classes="form-row"):
                        yield Label(t("Vision model"), classes="form-label")
                        yield Input(c["model"], id="ai-model")
                    with Horizontal(classes="form-row"):
                        yield Label(t("Chat model"), classes="form-label")
                        yield Input(c["chat_model"], id="ai-chat-model",
                                    placeholder=t("empty: the same as the vision model"))
                    with Horizontal(classes="form-row", id="ai-token-row"):
                        yield Label(t("API key"), classes="form-label", id="ai-token-label")
                        yield Input("", password=True, id="ai-token")
                    yield Label("", id="ai-key-note", classes="ai-note")
                    with Horizontal(classes="form-row"):
                        yield Label(t("Models"), classes="form-label")
                        yield Select([], allow_blank=True, prompt=t("Choose a model"), id="ai-model-list")
                    with Horizontal(classes="form-buttons"):
                        yield Button(t("Load models"), id="ai-models-load")
                        yield Button(t("Use for cataloguing"), id="ai-list-vision")
                        yield Button(t("Use for chat"), id="ai-list-chat")
                    yield Label("", id="ai-models-note", classes="ai-note")
                with Horizontal(classes="form-buttons"):
                    yield Button(t("Test connection"), id="ai-test", variant="primary")
                    yield Button(t("Save"), id="ai-save", variant="success")
                with Vertical(id="ai-ollama", classes="ai-box"):
                    yield Label(t("Not checked yet."), id="ai-ollama-state")
                    yield Label(t("Not installed? On this server run:") + f"\n  {aiclient.OLLAMA_INSTALL}\n"
                                + t("Without a GPU, prefer the light models: a 7B vision model can take "
                                    "minutes per answer on a CPU."),
                                id="ai-ollama-hint", classes="ai-note")
                    with Horizontal(classes="form-buttons"):
                        yield Button(t("Check Ollama"), id="ai-ollama-check")
                        yield Button(t("Install Ollama"), id="ai-ollama-install")
                    with Horizontal(classes="form-row"):
                        yield Label(t("Model"), classes="form-label")
                        yield Select(self.preset_options(), value=FIELDS, allow_blank=False, id="ai-ollama-preset")
                    with Horizontal(classes="form-buttons"):
                        yield Button(t("Download"), id="ai-ollama-pull", variant="primary")
                        yield Button(t("Use for chat"), id="ai-use-chat")
                        yield Button(t("Use for cataloguing"), id="ai-use-vision")
        with Grid(classes="status-grid", id="ai-cards"):
            yield StatusCard(t("Provider"), id="card-ai-provider")
            yield StatusCard(t("Connection"), id="card-ai-connection")
            yield StatusCard(t("MARC Replace"), id="card-ai-marc")
            yield StatusCard(t("💬  AI assistant"), id="card-aia-page")
        with Vertical(id="ai-hook", classes="ai-box"):
            with Horizontal(classes="ai-tool-row"):
                yield Label("", id="ai-hook-text", classes="ai-tool-text")
                yield Button(t("Open MARC Replace"), id="ai-marc", variant="primary")
            with Horizontal(classes="ai-tool-row"):
                yield Label("", id="ai-aia-text", classes="ai-tool-text")
                yield Button(t("Install, update or remove the assistant"), id="ai-assistant", variant="primary")

    def preset_options(self) -> list[tuple[str, str]]:
        """The download list: the typed models, then the presets, light first;
        ✓ on the ones the last check found in Ollama."""
        options = [(t("The models in the fields above"), FIELDS)]
        for model, label, _use in aiconf.OLLAMA_PRESETS:
            mark = "✓ " if aiclient.model_found("ollama", model, self.ollama_models) else ""
            options.append((f"{mark}{model} · {t(label)}", model))
        return options

    def on_mount(self) -> None:
        self.query_one("#ai-form").border_title = t(aiconf.LABELS[self.provider])
        self.query_one("#ai-ollama").border_title = t("Ollama on this server")
        self.query_one("#ai-hook").border_title = t("The AI tools")
        self.apply_provider(self.provider, keep_fields=True)
        self.refresh_cards()

    def on_resize(self) -> None:
        # Beside the provider list the fields get too narrow to show a whole
        # address ("ttp://localhost:11434"): stack them under it instead.
        self.set_class(self.size.width < 110, "-stacked")

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
                url, model, chat = saved["url"], saved["model"], saved["chat_model"]
            else:
                (url, model), chat = aiconf.DEFAULTS[provider], ""
            self.query_one("#ai-url", Input).value = url
            self.query_one("#ai-model", Input).value = model
            self.query_one("#ai-chat-model", Input).value = chat
            self.query_one("#ai-token", Input).value = ""
        self.query_one("#ai-form").border_title = t(aiconf.LABELS[provider])
        self.query_one("#ai-token-row").display = provider != "ollama"
        self.show_key_note()
        self.show_models(aimodels.fallback(provider, "not loaded yet"))
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
        chat = self.query_one("#ai-chat-model", Input).value.strip()
        c["chat_model"] = "" if chat == c["model"] else chat
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
            "ai-ollama-install": self.install_ollama,
            "ai-assistant": self.open_assistant,
            "ai-ollama-pull": self.pull_model,
            "ai-use-chat": lambda: self.use_preset("chat"),
            "ai-use-vision": lambda: self.use_preset("vision"),
            "ai-marc": self.open_marc_replace,
            "ai-models-load": self.load_models,
            "ai-list-vision": lambda: self.use_listed("vision"),
            "ai-list-chat": lambda: self.use_listed("chat"),
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
            if not self.app.env.demo:
                self.show_models(aimodels.from_ids(self.provider, self.check.models))
            msg = f"{t('Connected.')} {len(self.check.models)} {t('models')}"
            missing = self.missing(self.check.models)
            for model in missing:
                msg += " · " + t("the model ${model} is not among them", model=model)
            self.app.notify(msg, severity="warning" if missing else "information", timeout=6)
        elif not result.cancelled:
            self.check, self.check_error = None, result.error
            self.app.task_failed(t("Testing the AI provider"), result)
        self.refresh_cards()

    def missing(self, ids: list[str]) -> list[str]:
        """The vision and chat models of the fields that ids do not have."""
        c = self.values()
        wanted = dict.fromkeys(m for m in (c["model"], aiconf.chat_model(c)) if m)
        return [m for m in wanted if not aiclient.model_found(c["provider"], m, ids)]

    # ------------------------------------------------------------------
    # The provider's models (aimodels): live list or built-in one
    # ------------------------------------------------------------------
    def load_models(self) -> None:
        conf = self.values()
        demo = self.app.env.demo

        def job(reporter: Reporter) -> aimodels.Discovery:    # thread worker
            reporter.status(conf["url"])
            if demo:
                _demo_wait(reporter, 1.0)
                return aimodels.fallback(conf["provider"], "demo mode")
            return aimodels.discover(conf)

        run_with_loader(self.app, t("Loading the provider's models"), job, on_done=self._models_loaded)

    def _models_loaded(self, result: TaskResult) -> None:
        if result.ok:
            found: aimodels.Discovery = result.value
            if found.provider == self.provider:
                self.show_models(found)
            if found.live:
                self.app.notify(t("${n} models available with this key.", n=len(found.models)))
            else:
                self.app.notify(t("The live list could not be read (${reason}): showing the built-in list.",
                                  reason=t(found.reason)), severity="warning", timeout=8)
        elif not result.cancelled:
            self.app.task_failed(t("Loading the provider's models"), result)

    def model_options(self, found: aimodels.Discovery) -> list[tuple[str, str]]:
        """Both groups under their headers; 💳 on the advanced models."""
        options: list[tuple[str, str]] = []
        for tier_, header, value in ((aimodels.FREE, aimodels.FREE_HEADER, HEADERS[0]),
                                     (aimodels.PAID, aimodels.PAID_HEADER, HEADERS[1])):
            group = found.group(tier_)
            if not group:
                continue
            options.append((f"── {t(header)} ──", value))
            for m in group:
                badge = f"  {aimodels.PAID_BADGE} {t('paid')}" if tier_ == aimodels.PAID else ""
                options.append((f"   {m.id}{badge}", m.id))
        return options

    def show_models(self, found: aimodels.Discovery) -> None:
        self.discovery = found
        select = self.query_one("#ai-model-list", Select)
        select.set_options(self.model_options(found))
        self.show_models_note()

    def show_models_note(self) -> None:
        found = self.discovery
        if found is None:
            return
        name = t(aiconf.LABELS[found.provider])
        if found.live:
            parts = [t("Live list from ${name}: ${n} models.", name=name, n=len(found.models))]
        elif found.models:
            parts = [t("Built-in list (${reason}).", reason=t(found.reason))]
            if found.provider not in ("ollama", "compatible"):
                parts.append(t("Paste the API key and press Load models for the models your key can use."))
        else:
            parts = [t("Press Load models to read the models of this server.")]
        note = aimodels.BILLING_NOTE.get(found.provider, "")
        if note:
            parts.append(t(note))
        chosen = self.listed_model()
        if chosen and aimodels.tier(found.provider, chosen) == aimodels.PAID:
            parts.append(f"{aimodels.PAID_BADGE} " + t(aimodels.PAID_WARNING, provider=name))
        self.query_one("#ai-models-note", Label).update("\n".join(parts))

    def listed_model(self) -> str:
        value = self.query_one("#ai-model-list", Select).value
        return value if isinstance(value, str) and value not in HEADERS else ""

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "ai-model-list":
            event.stop()
            self.show_models_note()

    def use_listed(self, use: str) -> None:
        """Puts the model chosen in the list in the vision or chat field;
        Save keeps it. An advanced model is set too, with the warning."""
        model = self.listed_model()
        if not model:
            self.app.notify(t("Choose a model in the list first."), severity="warning")
            return
        field = "#ai-chat-model" if use == "chat" else "#ai-model"
        self.query_one(field, Input).value = model
        if self.discovery and aimodels.tier(self.provider, model) == aimodels.PAID:
            self.app.notify(t(aimodels.PAID_WARNING, provider=t(aiconf.LABELS[self.provider])),
                            severity="warning", timeout=8)
        self.app.notify(t("${model} set. Save to keep it.", model=model))

    def ollama_url(self) -> str:
        """Ollama's address: the field's when it is the provider, else the
        saved one, else the local default. The assistant plays no part."""
        if self.provider == "ollama":
            return self.query_one("#ai-url", Input).value.strip() or aiconf.OLLAMA_URL
        saved = self.saved()
        return saved["url"] if saved["provider"] == "ollama" else aiconf.OLLAMA_URL

    def check_ollama(self) -> None:
        url, demo = self.ollama_url(), self.app.env.demo

        def job(reporter: Reporter) -> tuple[str, list[str]]:
            reporter.status(url)
            if demo:
                _demo_wait(reporter, 1.2)
                return "0.12-demo", ["llama3.2:latest"]
            try:
                version = aiclient.ollama_version(url)
                reporter.progress(1, 2)
                return version, aiclient.check_connection({"provider": "ollama", "url": url, "model": ""}).models
            except RuntimeError as e:
                raise TaskFailed(str(e)) from None

        run_with_loader(self.app, t("Checking the local Ollama"), job, on_done=self._ollama_checked)

    def _ollama_checked(self, result: TaskResult) -> None:
        state = self.query_one("#ai-ollama-state", Label)
        if result.cancelled:
            return
        local = self.provider == "ollama"
        if not result.ok:
            state.update(t("Ollama is not answering at ${url}.", url=self.ollama_url()))
            self.ollama_models = []
            if local:
                self.check, self.check_error = None, result.error
            self._refresh_presets()
            self.refresh_cards()
            return
        version, models = result.value
        self.ollama_models = models
        parts = [f"Ollama {version}", f"{len(models)} {t('models')}"]
        if local:
            c, missing = self.values(), self.missing(models)
            self.check = aiclient.Check(aiclient.models_endpoint(c)[0], models, not missing)
            self.check_error = ""
            for model in dict.fromkeys(m for m in (c["model"], aiconf.chat_model(c)) if m):
                have = t("not downloaded yet") if model in missing else t("installed")
                parts.append(f"{model}: {have}")
        state.update(" · ".join(parts))
        self._refresh_presets()
        self.refresh_cards()

    def _refresh_presets(self) -> None:
        select = self.query_one("#ai-ollama-preset", Select)
        value = select.value
        select.set_options(self.preset_options())
        select.value = value

    def install_ollama(self) -> None:
        """Ollama's own install script, run by the installer behind Pac-Man."""
        from ..routines.common import failed, run_task, show_failure

        async def flow() -> None:
            title = t("Installing Ollama")
            result = await run_task(self.app, title, "ollama-install")
            if failed(result):
                await show_failure(self.app, title, result)
                return
            self.check_ollama()
        self.app.run_worker(flow(), group="routine", exclusive=True, exit_on_error=False)

    def open_assistant(self) -> None:
        from ..menus import Entry
        self.app.run_entry(Entry("💬  AI assistant on the staff home page", "ai-assistant", kind="native"),
                           after=self.refresh_cards)

    def selected_preset(self) -> str:
        value = self.query_one("#ai-ollama-preset", Select).value
        return value if isinstance(value, str) else FIELDS

    def models_to_pull(self) -> list[str]:
        """The chosen preset, or the models of the fields (Ollama only)."""
        preset = self.selected_preset()
        if preset != FIELDS:
            return [preset]
        if self.provider != "ollama":
            return []
        c = self.values()
        return list(dict.fromkeys(m for m in (c["model"], aiconf.chat_model(c)) if m))

    def use_preset(self, use: str) -> None:
        """Puts the chosen preset in the chat or the vision field (switching
        the provider to Ollama); Save keeps it."""
        model = self.selected_preset()
        if model == FIELDS:
            self.app.notify(t("Choose a model in the list first."), severity="warning")
            return
        kind = next((u for m, _label, u in aiconf.OLLAMA_PRESETS if m == model), "")
        if use == "vision" and kind == "chat":
            self.app.notify(t("${model} reads text only: MARC Replace needs a vision model.", model=model),
                            severity="warning", timeout=6)
            return
        if self.provider != "ollama":
            self.apply_provider("ollama")
            self.query_one("#ai-p-ollama", RadioButton).value = True
        field = "#ai-chat-model" if use == "chat" else "#ai-model"
        self.query_one(field, Input).value = model
        self.app.notify(t("${model} set. Save to keep it.", model=model))

    def pull_model(self) -> None:
        """Downloads into Ollama: needs Ollama answering, nothing else."""
        models = self.models_to_pull()
        if not models:
            self.app.notify(t("Choose a model in the list first."), severity="warning")
            return
        url, demo = self.ollama_url(), self.app.env.demo

        def job(reporter: Reporter) -> str:
            if demo:
                reporter.status(t("Downloading ${model}", model=", ".join(models)))
                _demo_wait(reporter, 3.0)
                return ", ".join(models)
            try:
                aiclient.ollama_version(url)
            except RuntimeError:
                raise TaskFailed(t("Ollama is not answering at ${url}. Install or start it first (Install Ollama).",
                                   url=url)) from None
            for model in models:
                if reporter.cancelled:
                    break
                reporter.log(t("Downloading ${model}", model=model))
                reporter.status(t("Downloading ${model}", model=model))
                last = [""]

                def progress(status: str, done: int, total: int) -> None:
                    if status != last[0]:
                        reporter.log(status)
                        reporter.status(f"{model}: {status}"[:60])
                        last[0] = status
                    if total:
                        reporter.progress(done, total)
                try:
                    aiclient.ollama_pull(url, model, progress, lambda: reporter.cancelled)
                except RuntimeError as e:
                    raise TaskFailed(f"{model}: {e}") from None
            return ", ".join(models)

        run_with_loader(self.app, t("Downloading the model into Ollama"), job, on_done=self._pulled)

    def _pulled(self, result: TaskResult) -> None:
        if result.ok:
            self.app.notify(f"{result.value}: {t('Done!')}", timeout=5)
            self.check_ollama()
        elif not result.cancelled:
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
        chat = aiconf.chat_model(saved)
        models = saved["model"] if chat == saved["model"] else f"{saved['model']} · {t('chat')}: {chat}"
        self.query_one("#card-ai-provider", StatusCard).set(
            name if ready else t("Not set up"), models if ready else t("Save a provider below"),
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

        on_page = marcreplace.assistant_installed(self.app.env.demo)
        self.query_one("#card-aia-page", StatusCard).set(
            t("Installed") if on_page else t("Not installed."), "ai_assistant.pl", "ok" if on_page else "warn")
        aia = self.query_one("#ai-aia-text", Label)
        if not ready:
            aia.update(t("AI assistant: set up and save an AI provider first."))
        elif on_page:
            aia.update(t("AI assistant: on the staff home page, answering with ${name} (${model}).",
                         name=name, model=chat))
        else:
            aia.update(t("AI assistant: ready to install on the staff home page (${model}).", model=chat))

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
