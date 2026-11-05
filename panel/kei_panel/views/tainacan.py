"""Tainacan's summary: the Control Dashboard's Tainacan tab.

The summary shows what is already known and cheap: --status-json (state,
addresses, events, the last diagnosis kept with the time it was read) and
the backup engine's status (last backup, last restore test). Nothing here
starts, stops or restarts anything, and the full diagnosis only runs when
the person asks for it (Tainacan, Diagnosis & maintenance). The tools are in
the Tainacan group of the sidebar (routines/platforms.py).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Grid

from .. import platforms
from ..i18n import t
from ..widgets.cards import LinkCard, StatusCard

# The cards of the summary, in order: (id, title).
SUMMARY_CARDS = (
    ("state", "Tainacan"),
    ("public", "Public home page"),
    ("events", "Events"),
    ("content", "Collections"),
    ("versions", "Versions"),
    ("backup", "Last backup"),
    ("restore-test", "Last restore test"),
)


class TainacanSummary(Grid):
    """The addresses and the summary cards; `prefix` keeps the ids apart
    where two summaries live in one screen (the section and the dashboard)."""

    def __init__(self, prefix: str, **kwargs):
        super().__init__(classes="status-grid", **kwargs)
        self.prefix = prefix

    def compose(self) -> ComposeResult:
        yield LinkCard(t("Collections (public site)"), id=f"{self.prefix}-link-site")
        yield LinkCard(t("Administration (WordPress)"), id=f"{self.prefix}-link-admin")
        for key, title in SUMMARY_CARDS:
            yield StatusCard(t(title), id=f"{self.prefix}-{key}")

    def show(self, state: platforms.TainacanState, docker: platforms.DockerState,
             backups: platforms.BackupState) -> None:
        site = self.query_one(f"#{self.prefix}-link-site", LinkCard)
        admin = self.query_one(f"#{self.prefix}-link-admin", LinkCard)
        site.set_url(state.url, t("The collections as visitors see them") if state.url else t("No address yet"),
                     "ok" if state.url else "")
        admin.set_url(state.admin_url, t("WordPress login of Tainacan's administrators") if state.admin_url
                      else t("No address yet"), "ok" if state.admin_url else "")
        for key, values in platforms.tainacan_summary(state, docker, backups).items():
            self.query_one(f"#{self.prefix}-{key}", StatusCard).set(*values)


async def read_tainacan(app, status: dict | None) -> tuple[platforms.TainacanState, platforms.DockerState,
                                                             platforms.BackupState]:
    """What the summary shows, from --status-json and the backup engine's
    status (both read only)."""
    tainacan = platforms.tainacan_from_status(status)
    docker = platforms.docker_from_status(status)
    backups = platforms.BackupState()
    if platforms.tainacan_installed(tainacan) and app.bridge.has_task("platform-backup-status"):
        try:
            out = await app.bridge.task("platform-backup-status", "tainacan")
            backups = platforms.backup_from_results(out.results)
        except Exception:  # the cards then say "not checked"
            backups = platforms.BackupState()
    return tainacan, docker, backups
