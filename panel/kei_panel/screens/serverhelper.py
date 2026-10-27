"""The AI server helper's screen (AI tools > Server helper).

  ┌ 🛠  Server helper (experimental) ──────────────────────────────┐
  │ ⚠ Potentially dangerous: the AI can be wrong ...               │
  │ Gemini (gemini-flash-latest): readings are sent to Google ...  │
  │ ┌ conversation ──────────────────────────────────────────────┐ │
  │ │ You: the catalogue search finds nothing                    │ │
  │ │ $ runuser -u kn-helper -- sudo -n .../kn-helper-action ... │ │
  │ │ Helper: Zebra is stopped ...                               │ │
  │ └────────────────────────────────────────────────────────────┘ │
  │ ┌ Proposed change ───────────────────────────────────────────┐ │
  │ │ runuser -u kn-helper -- sudo -n ... restart koha-common    │ │
  │ │ = systemctl restart koha-common · why · risk               │ │
  │ │ [Approve and run]  [Reject]                                │ │
  │ └────────────────────────────────────────────────────────────┘ │
  │ [question ...........................] [Send] [Log] [Back]     │
  └────────────────────────────────────────────────────────────────┘

The warning must be accepted once before the first use (ai-helper.conf).
A proposal runs only through Approve and run, then a second Yes on a box
that shows the exact command again; leaving the screen rejects it. The
model and every command run behind the Pac-Man loader (thread jobs).
"""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RichLog, Static

from .. import aiclient, aiconf, serverhelper
from ..i18n import t
from ..tasks import Reporter, TaskFailed, TaskResult, run_with_loader
from .dialogs import ConfirmScreen

WARNING = ("Potentially dangerous: this helper can restart services and change this server. The AI can be "
           "wrong. Every change shows its exact command and runs only after you approve it; read it before "
           "you approve. Everything is written to the helper's log.")
CLOUD_NOTE = ("Uses ${name} (${model}): the readings of this server (service states, log lines) are sent to "
              "that company. Passwords, keys and e-mail addresses are hidden first.")
LOCAL_NOTE = "Uses ${name} (${model}) on this server: nothing leaves the machine."


class ServerHelperScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "back", t("Back"))]

    def __init__(self, conf: dict[str, str], instance: str, language: str, demo: bool = False):
        super().__init__()
        self.conf, self.instance, self.demo = conf, instance, demo
        self.conversation = serverhelper.Conversation(language, instance)
        self.proposal: serverhelper.Proposal | None = None

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog -wide", id="helper"):
            yield Label("🛠  " + t("Server helper (experimental)"), classes="dialog-title")
            yield Label("⚠  " + t(WARNING), id="helper-warning", classes="ai-warning")
            yield Label(self.provider_note(), id="helper-provider", classes="dialog-note")
            yield RichLog(id="helper-log", wrap=True, markup=False, max_lines=2000)
            with Vertical(id="helper-proposal"):
                yield Static("", id="helper-command", classes="dialog-command", markup=False)
                yield Label("", id="helper-why", markup=False)
                with Horizontal(classes="dialog-buttons"):
                    yield Button(t("Approve and run"), id="helper-approve", variant="error")
                    yield Button(t("Reject"), id="helper-reject")
            with Horizontal(id="helper-setup-row"):
                yield Label("", id="helper-setup-note", classes="dialog-note")
                yield Button(t("Set up the helper"), id="helper-setup", variant="warning")
            with Horizontal(id="helper-ask"):
                yield Input(placeholder=t("What is wrong? For example: the catalogue search finds nothing"),
                            id="helper-input")
                yield Button(t("Send"), id="helper-send", variant="primary")
                yield Button(t("Helper log"), id="helper-audit")
                yield Button(t("Back"), id="helper-back")

    def on_mount(self) -> None:
        self.query_one("#helper-log").border_title = t("Conversation")
        self.query_one("#helper-proposal").border_title = t("Proposed change")
        self.query_one("#helper-proposal").display = False
        self.refresh_setup()
        if self.demo or serverhelper.accepted():
            self.query_one("#helper-input").focus()
        else:
            self.app.push_screen(
                ConfirmScreen(t("Server helper (experimental)"),
                              t(WARNING) + "\n\n" + self.provider_note() + "\n\n" + t("Use the server helper?"), danger=True),
                callback=self._consent)

    def provider_note(self) -> str:
        note = LOCAL_NOTE if self.conf["provider"] == "ollama" else CLOUD_NOTE
        return t(note, name=t(aiconf.LABELS[self.conf["provider"]]), model=aiconf.chat_model(self.conf))

    def audit(self, event: str, **fields: object) -> None:
        if not self.demo:
            serverhelper.audit(event, **fields)

    def _consent(self, yes: bool | None) -> None:
        if not yes:
            self.dismiss(None)
            return
        try:
            serverhelper.accept()
        except OSError as e:
            self.app.notify(str(e), severity="error")
        self.audit("accepted-warning")
        self.query_one("#helper-input").focus()

    def is_installed(self) -> bool:
        return self.demo or serverhelper.installed()

    def refresh_setup(self) -> None:
        ready = self.is_installed()
        self.query_one("#helper-setup-row").display = not ready
        self.query_one("#helper-send", Button).disabled = not ready
        self.query_one("#helper-setup-note", Label).update(
            "" if ready else t("Not set up yet: Set up the helper creates the system user ${user}, which may run "
                               "only the helper's fixed list of actions.", user=serverhelper.USER))

    def say(self, who: str, text: str, style: str = "") -> None:
        log = self.query_one("#helper-log", RichLog)
        line = Text(f"{who}: " if who else "", style="bold")
        line.append(text, style=style)
        log.write(line)

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    @on(Button.Pressed, "#helper-back")
    def action_back(self) -> None:
        if self.proposal:
            self._reject()
        self.dismiss(None)

    @on(Button.Pressed, "#helper-send")
    @on(Input.Submitted, "#helper-input")
    def send(self) -> None:
        box = self.query_one("#helper-input", Input)
        question = box.value.strip()
        if not question or not self.is_installed():
            return
        if self.proposal:
            self._reject()
        box.value = ""
        self.say(t("You"), question)
        conv, conf, demo, instance, audit = self.conversation, self.conf, self.demo, self.instance, self.audit

        def job(reporter: Reporter) -> serverhelper.Turn:        # thread worker
            chat = _demo_chat if demo else (lambda messages: aiclient.chat(conf, messages))
            runner = _demo_run if demo else (lambda a, args: serverhelper.run(a, args, instance))
            reporter.status(t("The AI is reading the server"))

            def step(command: str) -> None:
                reporter.log(command)
                audit("read", command=command)
            try:
                return conv.ask(question, chat, runner, step)
            except RuntimeError as e:
                raise TaskFailed(str(e)) from None

        run_with_loader(self.app, t("Asking the server helper"), job, on_done=self._answered)

    def _answered(self, result: TaskResult) -> None:
        if not result.ok:
            if not result.cancelled:
                self.say("", result.error or t("Unknown error."), "red")
            return
        turn: serverhelper.Turn = result.value
        for command, rc, out in turn.readings:
            self.say("$", command, "dim")
            tail = out.strip().splitlines()[-12:]
            for line in tail:
                self.say("", "  " + line, "dim" if rc == 0 else "yellow")
        for name in turn.refused:
            self.say("", t("Ignored an action outside the allowed list: ${action}", action=name or "?"), "yellow")
        if turn.say:
            self.say(t("Helper"), turn.say)
        self.show_proposal(turn.proposal)

    def show_proposal(self, p: serverhelper.Proposal | None) -> None:
        self.proposal = p
        box = self.query_one("#helper-proposal")
        box.display = p is not None
        if p is None:
            return
        command = serverhelper.command_text(p.action, p.args, self.instance)
        effect = serverhelper.effect_text(p.action, p.args, self.instance)
        self.query_one("#helper-command", Static).update(f"{command}\n= {effect}")
        parts = [x for x in (p.why and t("Why:") + " " + p.why, p.risk and t("Risk:") + " " + p.risk) if x]
        self.query_one("#helper-why", Label).update("\n".join(parts))
        self.audit("proposed", command=command, why=p.why, risk=p.risk, **self._who_answers())

    def _who_answers(self) -> dict[str, str]:
        return {"provider": self.conf["provider"], "model": aiconf.chat_model(self.conf)}

    @on(Button.Pressed, "#helper-reject")
    def _reject(self) -> None:
        p = self.proposal
        if not p:
            return
        self.audit("rejected", command=serverhelper.command_text(p.action, p.args, self.instance))
        self.conversation.ran(p, approved=False)
        self.say("", t("Rejected: nothing ran."), "yellow")
        self.show_proposal(None)

    @on(Button.Pressed, "#helper-approve")
    def approve(self) -> None:
        p = self.proposal
        if not p:
            return
        command = serverhelper.command_text(p.action, p.args, self.instance)
        effect = serverhelper.effect_text(p.action, p.args, self.instance)
        self.app.push_screen(
            ConfirmScreen(t("Run this command?"), t("It runs as root on this server now. Run it?"), danger=True,
                          preview=f"{command}\n\n= {effect}", preview_title=t("Exact command")),
            callback=lambda yes: self._run(p) if yes else None)

    def _run(self, p: serverhelper.Proposal) -> None:
        if p is not self.proposal:
            return
        command = serverhelper.command_text(p.action, p.args, self.instance)
        self.audit("approved", command=command, **self._who_answers())
        self.show_proposal(None)
        demo, instance = self.demo, self.instance

        def job(reporter: Reporter) -> tuple[int, str]:            # thread worker
            reporter.status(command[-60:])
            reporter.log(command)
            return _demo_run(p.action, p.args) if demo else serverhelper.run(p.action, p.args, instance)

        def done(result: TaskResult) -> None:
            rc, out = result.value if result.ok else (1, result.error or t("Cancelled"))
            self.audit("ran", command=command, rc=rc, output=out)
            self.conversation.ran(p, approved=True, rc=rc, out=out)
            self.say("$", command, "bold")
            for line in out.strip().splitlines()[-20:]:
                self.say("", "  " + line, "green" if rc == 0 else "red")
            self.say("", t("Done!") if rc == 0 else t("The command failed (exit ${rc}).", rc=rc),
                     "green" if rc == 0 else "red")

        run_with_loader(self.app, t("Running the approved command"), job, on_done=done)

    @on(Button.Pressed, "#helper-setup")
    def setup(self) -> None:
        from ..routines.common import failed, run_task, show_failure

        async def flow() -> None:
            title = t("Setting up the server helper")
            result = await run_task(self.app, title, "ai-helper-setup")
            if failed(result):
                await show_failure(self.app, title, result)
            else:
                self.audit("setup")
            self.refresh_setup()
        self.app.run_worker(flow(), group="routine", exclusive=True, exit_on_error=False)

    @on(Button.Pressed, "#helper-audit")
    def open_audit(self) -> None:
        from .logtail import LogTailScreen
        self.app.push_screen(LogTailScreen(t("Server helper log"), str(serverhelper.AUDIT_LOG)))


# ----------------------------------------------------------------------
# Demo mode: a model and a server that answer the same every time
# ----------------------------------------------------------------------
def _demo_chat(messages: list[dict[str, str]]) -> str:
    import json
    import time
    time.sleep(0.3)
    if not any(m["content"].startswith("Readings") for m in messages if m["role"] == "user"):
        return json.dumps({"say": "", "read": [{"action": "overview", "args": []}]})
    return json.dumps({"say": "Memcached is stopped, so Koha pages are slow. Restarting it should help.",
                       "read": [],
                       "propose": {"action": "restart", "args": ["memcached"],
                                   "why": "overview: memcached failed",
                                   "risk": "staff sessions stay; pages are slower for a few seconds"}})


def _demo_run(action: str, args: list[str]) -> tuple[int, str]:
    if action == "overview":
        return 0, "koha-common            active\napache2                active\nmemcached              failed\n"
    return 0, f"{' '.join(args)}: active"
