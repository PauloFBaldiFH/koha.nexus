"""TainacanView: Tainacan's own section, shown only with Tainacan installed.

The summary (also the dashboard's Tainacan tab) shows what is already known
and cheap: --status-json (state, addresses, events, the last diagnosis kept
with the time it was read) and the backup engine's status (last backup,
last restore test). Nothing here starts, stops or restarts anything, and
the full diagnosis only runs when the person asks for it. The buttons are
the installer's tasks, which check everything again: the diagnosis, the
logs (secrets blanked), the WordPress administrator, and the optional
events (Nexus Eventos over Events Manager: off until turned on after the
plan and a Yes; turning them off keeps their data and never turns off an
Events Manager that was there before unless the person says so).

Installing, removing and backing up Tainacan stay in Platforms.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Grid, Horizontal
from textual.widgets import Button, Label, Static

from .. import platforms
from ..glyphs import split_icon
from ..i18n import t
from ..widgets.cards import LinkCard, StatusCard
from ..widgets.pacman import PacmanLoader
from .base import SectionView

# The cards of the summary, in order: (id, title).
SUMMARY_CARDS = (
    ("state", "Tainacan"),
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


class TainacanActions:
    """The Tainacan tasks a view runs (needs self.app and self.refresh_data;
    self.tainacan_state is the last TainacanState read)."""

    async def tainacan_status(self) -> None:
        """The installer's full diagnosis, as a list. The installer keeps it
        (with the time it was read) for the summary; a failed read keeps
        the one before and says why."""
        from ..screens.dialogs import MessageScreen, TextScreen

        out = await self.app.bridge.task("tainacan-status")
        labels = (("status", t("Status")), ("url", t("Address")), ("health", t("Health")), ("reason", t("Reason")),
                  ("db", t("Database")), ("wordpress", "WordPress"), ("wordpress_version", t("WordPress version")),
                  ("tainacan_version", t("Tainacan version")), ("images_pinned", t("Images as fixed")),
                  ("collections", t("Collections")), ("items", t("Items")), ("attachments", t("Attachments")),
                  ("attachments_missing", t("Attachments missing on disk")), ("audit", t("Isolation rules")),
                  ("apache_site", t("Apache site")), ("last_backup", t("Last backup")), ("backups", t("Backups")),
                  ("disk_db", t("Database size")), ("disk_wp", t("Files size")), ("docker", "Docker"))
        if not out.ok:
            msg = out.last("error")
            keep = t("The summary keeps the diagnosis before, with the time it was read.")
            await self.app.push_screen_wait(MessageScreen(
                t("Tainacan diagnosis"), f"{msg[2]}\n\n{keep}" if msg and msg[2] else
                t("The diagnosis could not be read.") + "\n\n" + keep, kind="error"))
            self.refresh_data()
            return
        text = "\n".join(f"{label}: {out.get(key)}" for key, label in labels if out.get(key))
        checked = out.get("checked_at")
        if checked.isdigit():
            text += "\n\n" + t("Read at ${when}.", when=platforms.when(int(checked)))
        await self.app.push_screen_wait(TextScreen(t("Tainacan diagnosis"), text or t("Not checked")))
        self.refresh_data()

    async def tainacan_logs(self) -> None:
        from ..routines.common import run_task, show_done

        result = await run_task(self.app, t("Tainacan logs"), "tainacan-logs", "200")
        await show_done(self.app, t("Tainacan logs"), result)

    async def tainacan_credentials(self) -> None:
        from ..routines.common import run_task, show_done

        title = t("Tainacan administrator")
        result = await run_task(self.app, title, "tainacan-credentials")
        await show_done(self.app, title, result)

    # Events in Tainacan (installer: --task tainacan-events). Off until the
    # person turns them on; every step is the installer's, which checks
    # again what the buttons only follow.
    async def events_on(self) -> None:
        """The installer's plan, then the person's Yes, then events on."""
        from ..routines.common import run_task, show_done
        from ..screens.dialogs import ConfirmScreen, MessageScreen

        title = t("Turn events on")
        plan = await self.app.bridge.task("tainacan-events", "plan")
        if plan.get("plan") != "enable":
            await self.app.push_screen_wait(MessageScreen(
                title, plan.get("note") or t("Events cannot be turned on now."), kind="error"))
            self.refresh_data()
            return
        labels = (("dependency", "Events Manager"), ("plugin", "Nexus Eventos"), ("data", t("Data")),
                  ("undo", ""))
        steps = "\n".join(f"{label}: {plan.get(key)}" if label else plan.get(key)
                          for key, label in labels if plan.get(key))
        if not await self.app.push_screen_wait(ConfirmScreen(
                title, t("Turn events on in Tainacan? Its collections and items do not change."), preview=steps,
                preview_title=t("What will change on this server"))):
            return
        result = await run_task(self.app, title, "tainacan-events", "enable", "confirm")
        if result.cancelled:
            await self.app.push_screen_wait(MessageScreen(title, t(
                "Turning events on was stopped before the end, so events stay off. What was already put in is "
                "kept and used when you turn events on again."), kind="info"))
        else:
            await show_done(self.app, title, result, t("Events are on."))
        self.refresh_data()

    async def events_off(self) -> None:
        """Events off, their data kept. Events Manager: the person decides,
        and one that was there before stays on by default."""
        from ..routines.common import run_task, show_done
        from ..screens.dialogs import ChoiceScreen, ConfirmScreen

        title = t("Turn events off")
        state = getattr(self, "tainacan_state", platforms.TainacanState())
        how = await self.app.push_screen_wait(ChoiceScreen(
            title, t("Events, bookings, attendance and certificates are kept: turning events on again brings "
                     "them back. What happens to Events Manager?"), platforms.events_off_choices(state)))
        if how not in ("default", "keep-dependency", "dependency"):
            return
        if how == "dependency":
            question = t("Turn events off and also turn off Events Manager, which was in this WordPress before "
                         "Koha.Nexus? Whatever else uses it in this site stops too. No data is deleted.")
        else:
            question = t("Turn events off? No data is deleted.")
        if not await self.app.push_screen_wait(ConfirmScreen(title, question, danger=how == "dependency")):
            return
        result = await run_task(self.app, title, "tainacan-events", "disable",
                                *([] if how == "default" else [how]))
        await show_done(self.app, title, result, t("Events are off. Their data was kept."))
        self.refresh_data()

    async def events_status(self) -> None:
        """The installer's view of events: on or off, both plugins, the data."""
        from ..screens.dialogs import TextScreen

        out = await self.app.bridge.task("tainacan-events", "status")
        origin = {"ours": t("installed by Koha.Nexus"), "preexisting": t("was in this WordPress before")}

        def plugin(value: str | None, who: str = "") -> str:
            if not value or value == "absent":
                return t("not installed")
            version, _sep, active = value.partition("|")
            text = f"{version} ({t('active') if active == 'active' else t('inactive')})"
            return f"{text}, {who}" if who else text

        lines = [t("Events are on.") if out.get("events") == "on" else t("Events are off.")]
        if out.get("reason"):
            lines.append(f"{t('Reason')}: {out.get('reason')}")
        if out.get("dependency"):
            lines.append(f"Events Manager: {plugin(out.get('dependency'), origin.get(out.get('dependency_origin') or '', ''))}")
        if out.get("plugin"):
            lines.append(f"Nexus Eventos: {plugin(out.get('plugin'))}")
        for key, label in (("count_events", t("Events")), ("count_bookings", t("Bookings")),
                           ("count_passes", t("Bookings with a pass")), ("count_attendance", t("Attendance")),
                           ("count_certificates", t("Certificates"))):
            if out.get(key):
                lines.append(f"{label}: {out.get(key)}")
        if not out.ok:
            lines.append((out.last("error") or ("", "", t("Not checked")))[2])
        await self.app.push_screen_wait(TextScreen(t("Events in Tainacan"), "\n".join(lines)))


# The buttons of the section: (id, label). The events ones follow
# platforms.events_buttons.
SECTION_BUTTONS = (
    ("tainacan-status", "Diagnosis"),
    ("tainacan-logs", "Logs"),
    ("tainacan-credentials", "Administrator"),
)
EVENTS_BUTTONS = (
    ("on", "Turn events on"),
    ("off", "Turn events off"),
    ("status", "Events"),
)


class TainacanView(TainacanActions, SectionView):
    def compose(self) -> ComposeResult:
        _icon, title = split_icon(t(self.section.title or self.section.label))
        with Horizontal(classes="view-head"):
            yield Label(title, classes="view-title")
            yield Button(t("Refresh"), id="tainacan-refresh", classes="small")
        yield Label(t(self.section.prompt), classes="view-prompt")
        yield PacmanLoader(compact=True, plain=self.app.env.plain, colors=not self.app.env.no_color,
                           id="tainacan-loader")
        yield TainacanSummary("tn", id="tainacan-summary")
        with Horizontal(classes="form-buttons", id="tainacan-section-buttons"):
            for bid, label in SECTION_BUTTONS:
                yield Button(t(label), id=bid, classes="small")
        yield Static(t("Administrator: the WordPress account of Tainacan. Koha's accounts, the superlibrarian "
                       "included, are not WordPress accounts and get no access here."), classes="view-prompt",
                     markup=False)
        yield Label(t("Events"), classes="view-prompt")
        with Horizontal(classes="form-buttons", id="tainacan-events-buttons"):
            for key, label in EVENTS_BUTTONS:
                yield Button(t(label), id=f"events-{key}", classes="small")

    def on_mount(self) -> None:
        for key, _label in EVENTS_BUTTONS:
            self.query_one(f"#events-{key}").display = False
        self.refresh_data()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "tainacan-refresh":
            event.stop()
            self.refresh_data()
        elif bid in {b for b, _l in SECTION_BUTTONS}:
            event.stop()
            action = getattr(self, bid.replace("-", "_"))
            self.app.run_worker(action(), group="routine", exclusive=True, exit_on_error=False)
        elif bid.startswith("events-"):
            event.stop()
            action = getattr(self, "events_" + bid[len("events-"):])
            self.app.run_worker(action(), group="routine", exclusive=True, exit_on_error=False)

    @on(LinkCard.Pressed)
    def _link(self, event: LinkCard.Pressed) -> None:
        event.stop()
        if event.copy:
            self.app.copy_to_clipboard(event.url)
        else:
            self.app.open_url(event.url)

    def refresh_data(self) -> None:
        self.query_one("#tainacan-loader").display = True
        self.run_worker(self._load(), exclusive=True, group="tainacan", exit_on_error=False)

    async def _load(self) -> None:
        try:
            status = await self.app.bridge.status()
        except Exception:  # the cards then say "not checked"; never a crash
            status = {}
        finally:
            self.query_one("#tainacan-loader").display = False
        state, docker, backups = await read_tainacan(self.app, status)
        self.tainacan_state = state
        self.query_one(TainacanSummary).show(state, docker, backups)
        for key, on_ in platforms.events_buttons(state, self.app.bridge.has_task("tainacan-events")).items():
            self.query_one(f"#events-{key}").display = on_
        for bid, _label in SECTION_BUTTONS:
            self.query_one(f"#{bid}").display = self.app.bridge.has_task(bid)
        self.app.platforms_seen(status)
