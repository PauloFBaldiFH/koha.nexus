"""BackupView: the last backup at a glance, then the backup routines."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal
from textual.widgets import Button

from ..i18n import t
from ..widgets.cards import StatusCard
from .base import SectionView
from .dashboard import age, human_bytes


class BackupView(SectionView):
    def compose(self) -> ComposeResult:
        yield from self.heading()
        with Horizontal(classes="quick-actions"):
            # The newest backup straight into this PC's Downloads folder
            # (routines/backup.download_latest; over SSH: the scp command).
            yield Button(t("📥 Download latest backup"), id="backup-download", variant="success")
        with Grid(classes="status-grid"):
            yield StatusCard(t("Last backup"), id="bk-age")
            yield StatusCard(t("Size"), id="bk-size")
            yield StatusCard(t("Result"), id="bk-result")
        yield from self.cards()

    def on_mount(self) -> None:
        self.refresh_data()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "backup-download":
            event.stop()
            self.app.run_native("backup-download")

    def refresh_data(self) -> None:
        self.run_worker(self._load(), exclusive=True, group="backup-status", exit_on_error=False)

    async def _load(self) -> None:
        try:
            b = (await self.app.bridge.status()).get("backup", {})
        except Exception as e:
            self.query_one("#bk-age", StatusCard).set("-", str(e)[:60], "bad")
            return
        self.query_one("#bk-age", StatusCard).set(age(b.get("last_epoch")), b.get("last_file") or "-")
        self.query_one("#bk-size", StatusCard).set(human_bytes(b.get("last_size")))
        ok = b.get("last_result") == "ok"
        self.query_one("#bk-result", StatusCard).set(b.get("last_result") or "-", "", "ok" if ok else "warn")
