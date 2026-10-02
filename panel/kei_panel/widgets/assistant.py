"""AssistantPanel (Module 2): the AI chat on the dashboard.

  ┌ AI assistant ─────────────────── Google Gemini · read-only ─ [New chat] ┐
  │ you        who is the last patron with 4 overdue books and 144 in fines? │
  │ assistant  Ana Souza (card C0101) has 4 overdue loans and 144.00 ...     │
  │            [Ana Souza]                               <- link chips       │
  │ ┌ Change waiting for your confirmation ──────────────────────────────┐   │
  │ │ UPDATE accountlines SET ... LIMIT 2          2 rows  [Confirm] [Cancel]│
  │ └────────────────────────────────────────────────────────────────────┘   │
  │ [Ask about books, patrons, reports, settings...              ] [Send]   │
  └──────────────────────────────────────────────────────────────────────────┘

Every question runs as one thread job behind the Pac-Man loader
(run_with_loader): the model's round trips and the read-only queries never
block the screen, and Esc cancels. Blue text in an answer is a link (click),
and the same links follow the answer as chips (Tab, Enter; Ctrl+O jumps to
the first one). A change is never run by the model: it arrives as a
ProposalCard, and only Confirm (then a last Yes) runs it.
"""

from __future__ import annotations

import asyncio

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.markup import escape
from textual.message import Message
from textual.widgets import Button, Input, Label, Static

from .. import aiconf, assistant
from ..assistant import actions, links
from ..assistant import db as dbmod
from ..assistant.agent import Turn
from ..assistant.tools import Proposal
from ..i18n import t
from ..tasks import Reporter, TaskFailed, TaskResult, run_with_loader

EXAMPLES = (
    "that book about the clown that was made into a movie",
    "who is the last patron with 4 overdue books and 144 in fines?",
    "where do I rebuild the search index?",
)


class OpenRef(Message):
    def __init__(self, key: str) -> None:
        super().__init__()
        self.key = key


class MessageBody(Static):
    """An answer's text; its blue links run open_ref here."""

    def action_open_ref(self, key: str) -> None:
        self.post_message(OpenRef(key))


class RefChip(Button):
    def __init__(self, key: str, label: str) -> None:
        super().__init__(label[:40], classes="ref-chip")
        self.key = key

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.post_message(OpenRef(self.key))


class ProposalCard(Vertical):
    class Decided(Message):
        def __init__(self, card: "ProposalCard", confirmed: bool) -> None:
            super().__init__()
            self.card, self.confirmed = card, confirmed

    def __init__(self, proposal: Proposal) -> None:
        super().__init__(classes="proposal-card")
        self.proposal = proposal

    def compose(self) -> ComposeResult:
        p = self.proposal
        yield Label(p.summary, classes="proposal-summary", markup=False)
        if p.kind == "sql":
            yield Static(p.run_sql, classes="proposal-sql", markup=False)
            yield Label(t("Touches at most ${rows} rows. A safety backup runs first when available.",
                          rows=p.rows), classes="proposal-note")
        else:
            yield Static(f"{t(p.label)}   (config.sh --run {p.action})", classes="proposal-sql", markup=False)
            yield Label(t("Runs the panel's own routine, exactly as from its menu."), classes="proposal-note")
        with Horizontal(classes="proposal-buttons"):
            yield Button(t("Confirm"), classes="proposal-confirm", variant="warning")
            yield Button(t("Cancel"), classes="proposal-cancel")

    def on_mount(self) -> None:
        self.border_title = t("Change waiting for your confirmation")

    @on(Button.Pressed, ".proposal-confirm")
    def _confirm(self, event: Button.Pressed) -> None:
        event.stop()
        self.post_message(self.Decided(self, True))

    @on(Button.Pressed, ".proposal-cancel")
    def _cancel(self, event: Button.Pressed) -> None:
        event.stop()
        self.post_message(self.Decided(self, False))

    def settle(self, state: str, note: str) -> None:
        self.proposal.state = state
        for b in self.query(Button):
            b.disabled = True
        self.query_one(".proposal-note", Label).update(note)
        self.set_class(True, f"-{state}")


class ChatMessage(Vertical):
    def __init__(self, role: str, text: str = "", turn: Turn | None = None,
                 verified: dict[str, str] | None = None) -> None:
        super().__init__(classes=f"chat-msg -{role}")
        self.role, self.text, self.turn = role, text, turn
        self.verified = verified or {}

    def compose(self) -> ComposeResult:
        who = {"user": t("you"), "assistant": t("assistant"), "error": t("error")}[self.role]
        with Horizontal(classes="chat-row"):
            yield Label(who, classes="chat-who")
            if self.role == "assistant":
                yield MessageBody(links.render(self.text, self.verified), classes="chat-text")
            else:
                yield Static(self.text, classes="chat-text", markup=False)
        chips = [(k, lbl) for k, lbl in links.refs(self.text) if k in self.verified]
        if chips:
            with Horizontal(classes="ref-chips"):
                for key, label in chips[:8]:
                    yield RefChip(key, label)
        for p in (self.turn.proposals if self.turn else []):
            yield ProposalCard(p)


class AssistantPanel(Vertical):
    BINDINGS = [
        Binding("ctrl+o", "first_link", t("Open link")),
        Binding("ctrl+n", "new_chat", t("New chat")),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent = None
        self._agent_conf: dict | None = None
        self.db = None

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        with Horizontal(classes="assistant-head"):
            yield Label("", id="assistant-provider")
            yield Button(t("New chat"), id="assistant-clear", classes="small")
        with Vertical(id="assistant-setup"):
            yield Label("", id="assistant-setup-text")
            with Horizontal(classes="form-buttons"):
                yield Button(t("Set up read-only access"), id="assistant-provision", variant="primary")
                yield Button(t("AI setup"), id="assistant-goto-ai")
        yield VerticalScroll(id="assistant-log")
        with Horizontal(id="assistant-input-row"):
            yield Input(placeholder=t("Ask about books, patrons, reports, settings..."), id="assistant-input")
            yield Button(t("Send"), id="assistant-send", variant="primary")

    def on_mount(self) -> None:
        self.border_title = t("AI assistant")
        self.db = assistant.make_db(self.app.env)
        self.refresh_state()
        self.query_one("#assistant-log").mount(ChatMessage(
            "assistant", t("Ask me about the catalogue, patrons, reports, settings or panel screens. "
                           "I only read: any change waits for your Confirm.") + "\n"
            + "\n".join(f"- {t(e)}" for e in EXAMPLES)))

    # ------------------------------------------------------------------
    # State: is there a provider (Module 1) and the read-only account?
    # ------------------------------------------------------------------
    def refresh_state(self) -> None:
        env = self.app.env
        c = assistant.provider(env)
        db_ready = self.db.ready()
        if env.demo:
            who = t("Demo model")
        elif c:
            who = f"{t(aiconf.LABELS[c['provider']])} · {c['model']}"
        else:
            who = t("No AI provider yet")
        self.query_one("#assistant-provider", Label).update(f"{who} · {t('read-only')}")
        missing = []
        if not c and not env.demo:
            missing.append(t("choose an AI provider in AI setup"))
        if not db_ready:
            missing.append(t("set up the assistant's read-only database access"))
        setup = self.query_one("#assistant-setup")
        setup.display = bool(missing)
        if missing:
            self.query_one("#assistant-setup-text", Label).update(t("Before the first question:") + " "
                                                                  + "; ".join(missing) + ".")
            self.query_one("#assistant-provision").display = not db_ready
        if self.agent is None or c != self._agent_conf:
            self.agent = assistant.make_agent(env, self.db)
            self._agent_conf = c

    def ready(self) -> bool:
        return self.agent is not None and self.db.ready()

    # ------------------------------------------------------------------
    # Asking
    # ------------------------------------------------------------------
    @on(Input.Submitted, "#assistant-input")
    @on(Button.Pressed, "#assistant-send")
    def send(self, event=None) -> None:
        if event:
            event.stop()
        box = self.query_one("#assistant-input", Input)
        question = box.value.strip()
        if not question:
            return
        self.refresh_state()
        if not self.ready():
            self.app.notify(t("The assistant is not set up yet."), severity="warning")
            return
        box.value = ""
        self.add(ChatMessage("user", question))
        agent = self.agent

        def job(reporter: Reporter) -> Turn:
            try:
                return agent.ask(question, reporter, cancelled=lambda: reporter.cancelled)
            except InterruptedError:
                raise TaskFailed(t("Cancelled")) from None
            except (RuntimeError, dbmod.DBError) as e:
                raise TaskFailed(str(e)) from None

        def done(result: TaskResult) -> None:
            if result.ok:
                self.add(ChatMessage("assistant", result.value.answer, result.value, dict(agent.ctx.refs)))
            elif not result.cancelled:
                self.add(ChatMessage("error", result.error))
            box.focus()

        run_with_loader(self.app, t("AI assistant"), job, on_done=done)

    def add(self, msg: ChatMessage) -> None:
        log = self.query_one("#assistant-log", VerticalScroll)
        log.mount(msg)
        log.call_after_refresh(log.scroll_end, animate=False)

    def action_new_chat(self) -> None:
        if self.agent:
            self.agent.reset()
        self.query_one("#assistant-log").remove_children()
        self.query_one("#assistant-input").focus()

    def action_first_link(self) -> None:
        chips = list(self.query(RefChip))
        last = list(self.query(ChatMessage))
        mine = [c for c in chips if last and c in last[-1].query(RefChip)]
        target = (mine or chips[-1:] or [None])[0]
        if target:
            target.focus()

    @on(Button.Pressed, "#assistant-clear")
    def _clear(self, event: Button.Pressed) -> None:
        event.stop()
        self.action_new_chat()

    @on(Button.Pressed, "#assistant-goto-ai")
    def _goto_ai(self, event: Button.Pressed) -> None:
        event.stop()
        self.screen.action_show("ai")

    # ------------------------------------------------------------------
    # The read-only account (root, once)
    # ------------------------------------------------------------------
    @on(Button.Pressed, "#assistant-provision")
    def provision(self, event: Button.Pressed | None = None) -> None:
        if event:
            event.stop()
        env = self.app.env

        def job(reporter: Reporter) -> str:
            reporter.status(t("Creating the read-only database account"))
            if env.demo:
                return "demo"
            try:
                return dbmod.provision(env.instance)
            except (dbmod.DBError, OSError, Exception) as e:   # shown, never a crash
                raise TaskFailed(str(e)) from None

        def done(result: TaskResult) -> None:
            if result.ok:
                self.app.notify(t("Read-only access ready (${db}).", db=result.value), timeout=5)
            else:
                self.app.task_failed(t("Set up read-only access"), result)
            self.refresh_state()

        run_with_loader(self.app, t("Set up read-only access"), job, on_done=done)

    # ------------------------------------------------------------------
    # Links
    # ------------------------------------------------------------------
    @on(OpenRef)
    def open_ref(self, event: OpenRef) -> None:
        event.stop()
        from ..screens.record import open_ref
        open_ref(self.app, self.agent.ctx if self.agent else None, event.key)

    # ------------------------------------------------------------------
    # Proposals: nothing runs before Confirm, then a last Yes
    # ------------------------------------------------------------------
    @on(ProposalCard.Decided)
    def decided(self, event: ProposalCard.Decided) -> None:
        event.stop()
        card, p = event.card, event.card.proposal
        if not event.confirmed:
            card.settle("cancelled", t("Cancelled: nothing was changed."))
            return
        if p.kind == "panel_action":
            entry = actions.entry_for(p)
            card.settle("done", t("Started: ${label}.", label=t(entry.label)))
            self.app.run_entry(entry)
            return
        from ..screens.dialogs import ConfirmScreen
        self.app.push_screen(
            ConfirmScreen(t("Run this change?"), escape(p.run_sql) + "\n\n" + t("Rows: ${rows}", rows=p.rows)),
            callback=lambda yes: self.run_sql(card) if yes else None)

    def run_sql(self, card: ProposalCard) -> None:
        p, app = card.proposal, self.app
        demo_db = self.db if app.env.demo else None

        async def job(reporter: Reporter) -> int:
            if app.bridge.supports(actions.BACKUP_VERB[0]) and not app.env.demo:
                reporter.status(t("Saving a safety backup"))
                rc = await app.bridge.run_verb(actions.BACKUP_VERB, reporter)
                if rc != 0:
                    raise TaskFailed(t("The safety backup failed: nothing was changed."), rc)
            reporter.status(t("Applying the change"))
            if demo_db is not None:
                return await asyncio.to_thread(demo_db.execute, p.run_sql)
            return await asyncio.to_thread(actions.run_sql, app.env.instance, p)

        def done(result: TaskResult) -> None:
            if result.ok:
                card.settle("done", t("Done: ${rows} rows changed.", rows=result.value))
            elif result.cancelled:
                card.settle("cancelled", t("Cancelled."))
            else:
                card.settle("failed", t("Failed: ${error}", error=result.error))
                app.task_failed(t("Run this change?"), result)

        run_with_loader(app, t("Applying the change"), job, on_done=done)
