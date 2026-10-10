"""BackupView: the last backup at a glance, the compression of new backups,
then the backup routines."""

from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.widgets import Button, Label, Select

from ..i18n import t
from ..widgets.cards import StatusCard
from .base import SectionView
from .dashboard import backup_card, human_bytes

# BACKUP_COMPRESSION in backup.conf (installer: backup_set_codec). Restores
# read any of them, whatever this setting says.
CODECS = {
    "gz": "Gzip (.sql.gz) · opens anywhere",
    "zst": "Zstandard (.sql.zst) · fast and smaller: large catalogs",
    "xz": "XZ / LZMA (.sql.xz) · smallest, slow to make: long-term storage",
}
# The last nightly run, as backup_sql.log tells it (kei_backup_summary).
RESULTS = {
    "ok": ("OK", "ok"),
    "failed": ("FAILED", "bad"),
    "skipped": ("Skipped (busy)", "warn"),
    "none": ("Not run yet", "warn"),
}
CODEC_NOTE = ("Used by the nightly backup, manual backups and the safety copies made before a change. "
              "Restore database recognises .sql, .sql.gz, .sql.zst and .sql.xz on its own.")


class BackupView(SectionView):
    def __init__(self, section):
        super().__init__(section)
        self.codec = ""          # the saved setting, once the installer answered

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
        with Vertical(id="bk-codec-box", classes="hub-box"):
            with Horizontal(classes="form-row"):
                yield Label(t("Compression"), classes="form-label")
                yield Select([(t(v), k) for k, v in CODECS.items()], value="gz", allow_blank=False,
                             id="bk-codec", disabled=True)
            yield Label(t(CODEC_NOTE), id="bk-codec-note", classes="ai-note")
        yield from self.cards()

    def on_mount(self) -> None:
        self.query_one("#bk-codec-box").border_title = t("New backups")
        self.refresh_data()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "backup-download":
            event.stop()
            self.app.run_native("backup-download")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "bk-codec":
            return
        event.stop()
        value = event.value if isinstance(event.value, str) else ""
        # The value the installer reported (on load) changes nothing.
        if not self.codec or value == self.codec or value not in CODECS:
            return
        self.run_worker(self._set_codec(value), exclusive=True, group="routine", exit_on_error=False)

    async def _set_codec(self, codec: str) -> None:
        from ..routines.common import failed, run_task, show_failure
        title = t("Compression")
        result = await run_task(self.app, t("Saving the backup settings"), "backup-compression", codec)
        if failed(result):
            await show_failure(self.app, title, result)
            self._show_codec(self.codec)
            return
        self._show_codec(codec)
        self.app.notify(t("New backups: ${name}", name=t(CODECS[codec]).split(" · ")[0]))

    def _show_codec(self, codec: str, used: str = "") -> None:
        self.codec = codec if codec in CODECS else "gz"
        select = self.query_one("#bk-codec", Select)
        select.value = self.codec
        select.disabled = False
        note = t(CODEC_NOTE)
        if used and used != self.codec:
            # zstd or xz missing on the server: the nightly script falls back.
            note += "\n" + t("The program for this compression is missing: backups are made with gzip until "
                             "it is installed (choose the compression again to install it).")
        self.query_one("#bk-codec-note", Label).update(note)

    def refresh_data(self) -> None:
        self.run_worker(self._load(), exclusive=True, group="backup-status", exit_on_error=False)

    async def _load(self) -> None:
        try:
            info = await self.app.bridge.task("info")
            self._show_codec(info.get("compression", "gz"), info.get("compression_used", ""))
        except Exception:
            pass
        try:
            b = (await self.app.bridge.status()).get("backup", {})
        except Exception as e:
            self.query_one("#bk-age", StatusCard).set("-", str(e)[:60], "bad")
            return
        self.query_one("#bk-age", StatusCard).set(*backup_card(b))
        self.query_one("#bk-size", StatusCard).set(human_bytes(b.get("last_size")))
        text, state = RESULTS.get(b.get("last_result") or "none", RESULTS["none"])
        note = t("Last nightly backup")
        if b.get("log_epoch"):
            note += " · " + time.strftime("%Y-%m-%d %H:%M", time.localtime(int(b["log_epoch"])))
        self.query_one("#bk-result", StatusCard).set(t(text), note, state)
