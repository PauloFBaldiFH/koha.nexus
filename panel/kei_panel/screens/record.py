"""Where a blue link of the assistant goes.

  page:<section id>   the panel switches to that screen, at once
  anything else       the record is read (get_record, read-only account)
                      behind the Pac-Man loader, then shown in RecordScreen:
                      its fields, its own links (a patron's loans open their
                      books) and its address in the staff interface.
"""

from __future__ import annotations

import os

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.markup import escape
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from ..assistant import links, tools
from ..i18n import t
from ..menus import SECTIONS
from ..tasks import Reporter, TaskFailed, TaskResult, run_with_loader

STAFF_BASE = os.environ.get("KEI_STAFF_URL", "http://localhost:8080").rstrip("/")
TITLES = {"biblio": "Book", "patron": "Patron", "report": "Saved report", "syspref": "System preference",
          "page": "Page"}
HIDDEN = {"link", "items", "loans", "score"}


def staff_url(kind: str, rid: str) -> str:
    if kind == "page":
        where = tools.PAGES.get(rid, ("", "", ""))[1]
        return STAFF_BASE + where if where.startswith("/") else ""
    path = tools.STAFF_PATHS.get(kind)
    return STAFF_BASE + path.format(id=rid) if path else ""


def open_ref(app, ctx: tools.Context | None, key: str) -> None:
    kind, _, rid = key.partition(":")
    if kind == "page" and rid in {s.id for s in SECTIONS}:
        app.screen.action_show(rid)
        return
    if ctx is None:
        return

    def job(reporter: Reporter) -> dict:
        reporter.status(t("Opening the record"))
        try:
            return tools.get_record(ctx, {"kind": kind, "id": rid})
        except tools.ToolError as e:
            raise TaskFailed(str(e)) from None

    def done(result: TaskResult) -> None:
        if result.ok:
            app.push_screen(RecordScreen(kind, rid, result.value, ctx))
        elif not result.cancelled:
            app.task_failed(t(TITLES.get(kind, "Record")), result)

    run_with_loader(app, t("Opening the record"), job, on_done=done)


def record_lines(rec: dict) -> str:
    rows = [f"[b]{escape(k)}[/b]  {escape(str(v))}" for k, v in rec.items()
            if k not in HIDDEN and v not in (None, "")]
    return "\n".join(rows)


def sub_rows(rec: dict, verified: dict[str, str]) -> str:
    out = []
    for item in rec.get("items") or []:
        state = t("on loan until ${d}", d=(item.get("onloan") or "")[:10]) if item.get("onloan") else t("available")
        out.append(f"- {escape(item.get('barcode') or '')}  {escape(item.get('itemcallnumber') or '')}  {state}")
    for loan in rec.get("loans") or []:
        late = "  [b red]" + t("overdue") + "[/]" if loan.get("overdue") == "1" else ""
        out.append(f"- {links.render(loan.get('link', ''), verified)}  {t('due')} "
                   f"{escape((loan.get('date_due') or '')[:10])}{late}")
    return "\n".join(out)


class RecordBody(Static):
    """Links inside a record (a patron's loans) open the next record."""

    def __init__(self, text: str, ctx: tools.Context | None, **kw) -> None:
        super().__init__(text, **kw)
        self.ctx = ctx

    def action_open_ref(self, key: str) -> None:
        app = self.app
        self.screen.dismiss(None)
        open_ref(app, self.ctx, key)


class RecordScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape,enter", "close", t("Close"))]

    def __init__(self, kind: str, rid: str, rec: dict, ctx: tools.Context | None = None) -> None:
        super().__init__()
        self.kind, self.rid, self.rec, self.ctx = kind, rid, rec, ctx

    def compose(self) -> ComposeResult:
        verified = dict(self.ctx.refs) if self.ctx else {}
        label = links.refs(self.rec.get("link", ""))
        with Vertical(classes="dialog record-dialog"):
            yield Label(f"{t(TITLES.get(self.kind, 'Record'))}: {label[0][1] if label else self.rid}",
                        classes="dialog-title", markup=False)
            with VerticalScroll(classes="record-body"):
                yield Static(record_lines(self.rec))
                subs = sub_rows(self.rec, verified)
                if subs:
                    yield RecordBody(subs, self.ctx, classes="record-sub")
            url = staff_url(self.kind, self.rid)
            if url:
                yield Label(t("Staff interface:") + f" {url}", classes="record-url", markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("Close"), id="close", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#close").focus()

    @on(Button.Pressed, "#close")
    def action_close(self) -> None:
        self.dismiss(None)
