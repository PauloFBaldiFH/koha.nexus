"""DatabaseView: Koha's tables, largest first (read-only).

Loading the list is data processing, so it runs behind the Pac-Man modal
(tasks.run_with_loader). Changes to the database stay with the bash
routines, which take a verified backup first.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Label

from ..i18n import t
from ..tasks import Reporter, TaskResult, run_with_loader
from .base import SectionView
from .dashboard import human_bytes


class DatabaseView(SectionView):
    loaded = False

    def compose(self) -> ComposeResult:
        with Horizontal(classes="view-head"):
            yield from self.heading()
            yield Button(t("Refresh"), id="load-tables", classes="small")
        yield Label("", id="db-summary", classes="view-prompt")
        table = DataTable(id="tables", zebra_stripes=True, cursor_type="row")
        table.add_column(t("Table"), key="name")
        table.add_column(t("Rows"), key="rows")
        table.add_column(t("Size"), key="size")
        yield table
        yield from self.cards()

    def on_show(self) -> None:
        if not self.loaded:
            self.load_tables()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "load-tables":
            self.load_tables()

    def load_tables(self) -> None:
        self.loaded = True

        async def job(reporter: Reporter):
            reporter.status(t("Reading the database"))
            return await self.app.bridge.koha_tables(reporter)

        run_with_loader(self.app, t("Reading Koha's tables"), job, on_done=self._show)

    def _show(self, result: TaskResult) -> None:
        if not result.ok:
            self.app.task_failed(t("Reading Koha's tables"), result)
            return
        table = self.query_one("#tables", DataTable)
        table.clear()
        total = 0
        for name, rows, size in result.value:
            total += size
            table.add_row(name, f"{rows:,}", human_bytes(size), key=name)
        self.query_one("#db-summary", Label).update(
            f"{len(result.value)} {t('tables')} · {human_bytes(total)}")
