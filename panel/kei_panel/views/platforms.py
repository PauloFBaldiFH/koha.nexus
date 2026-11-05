"""PlatformsView: the platforms this panel knows, one card each.

Read only. Each card keeps the four facts apart (platforms.py): supported
by this panel, installation detected, services, functional health (not
verified yet). Koha keeps its own "Install Koha server" entry. Docker and
Tainacan can be installed from here: the installer's plan is shown first
and nothing happens without a Yes. Tainacan's card also has its diagnosis,
backup, restore (tested first in an isolated copy) and uninstall; AtoM and
DSpace are planned. The "Platform backups" card shows the common backup
engine (encryption key, restic repository, cloud copy, schedule, last
restore test) with its own buttons; the recovery phrase is passed to the
installer in the environment, never on its command line.
"""

from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, VerticalScroll
from textual.widgets import Button, Label

from .. import platforms
from ..glyphs import split_icon
from ..i18n import t
from ..widgets.cards import StatusCard
from ..widgets.pacman import PacmanLoader
from .base import SectionView


class PlatformsView(SectionView):
    def compose(self) -> ComposeResult:
        _icon, title = split_icon(t(self.section.title or self.section.label))
        with Horizontal(classes="view-head"):
            yield Label(title, classes="view-title")
            yield Button(t("Refresh"), id="platforms-refresh", classes="small")
        yield Label(t(self.section.prompt), classes="view-prompt")
        yield PacmanLoader(compact=True, plain=self.app.env.plain, colors=not self.app.env.no_color,
                           id="platforms-loader")
        with Grid(classes="status-grid", id="platform-cards"):
            for p in platforms.CATALOG:
                yield StatusCard(f"{p.name}: {t(p.role)}", id=f"platform-{p.id}")
            yield StatusCard(t("Web proxy"), id="platform-proxy")
            yield StatusCard("Docker", id="platform-docker")
            yield StatusCard(t("Platform backups"), id="platform-backups")
        with Horizontal(classes="form-buttons"):
            yield Button(t("Install Docker"), id="platforms-docker-install", classes="small")
            yield Button(t("Remove Docker"), id="platforms-docker-remove", classes="small")
        with Horizontal(classes="form-buttons", id="platforms-tainacan-buttons"):
            for key, label in TAINACAN_BUTTONS:
                yield Button(t(label), id=f"tainacan-{key}", classes="small")
        with Horizontal(classes="form-buttons", id="platforms-backup-buttons"):
            for key, label in BACKUP_BUTTONS:
                yield Button(t(label), id=f"pbackup-{key}", classes="small")

    def on_mount(self) -> None:
        self.query_one("#platforms-docker-install").display = False
        self.query_one("#platforms-docker-remove").display = False
        for key, _label in TAINACAN_BUTTONS:
            self.query_one(f"#tainacan-{key}").display = False
        for key, _label in BACKUP_BUTTONS:
            self.query_one(f"#pbackup-{key}").display = False
        self.query_one("#platform-backups").display = False
        self.refresh_data()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "platforms-refresh":
            event.stop()
            self.refresh_data()
        elif event.button.id == "platforms-docker-install":
            event.stop()
            self.app.run_worker(self.install_docker(), group="routine", exclusive=True, exit_on_error=False)
        elif event.button.id == "platforms-docker-remove":
            event.stop()
            self.app.run_worker(self.remove_docker(), group="routine", exclusive=True, exit_on_error=False)
        elif event.button.id and event.button.id.startswith("tainacan-"):
            event.stop()
            action = getattr(self, "tainacan_" + event.button.id[len("tainacan-"):].replace("-", "_"))
            self.app.run_worker(action(), group="routine", exclusive=True, exit_on_error=False)
        elif event.button.id and event.button.id.startswith("pbackup-"):
            event.stop()
            action = getattr(self, "backup_" + event.button.id[len("pbackup-"):].replace("-", "_"))
            self.app.run_worker(action(), group="routine", exclusive=True, exit_on_error=False)

    def refresh_data(self) -> None:
        self.query_one("#platforms-loader").display = True
        self.run_worker(self._load(), exclusive=True, group="platforms", exit_on_error=False)

    async def _load(self) -> None:
        try:
            status = await self.app.bridge.status()
        except Exception:  # the cards then say "not checked"; never a crash
            status = {"koha_installed": self.app.koha_installed}
        finally:
            self.query_one("#platforms-loader").display = False
        self.show(platforms.from_status(status))
        self.query_one("#platform-proxy", StatusCard).set(
            *platforms.describe_proxy(platforms.proxy_from_status(status)))
        docker = platforms.docker_from_status(status)
        self.query_one("#platform-docker", StatusCard).set(*platforms.describe_docker(docker))
        self.query_one("#platforms-docker-install").display = (
            platforms.docker_can_install(docker) and self.app.bridge.has_task("docker-plan"))
        self.query_one("#platforms-docker-remove").display = (
            platforms.docker_can_remove(docker) and self.app.bridge.has_task("docker-remove"))
        tainacan = platforms.tainacan_from_status(status)
        self.query_one("#platform-tainacan", StatusCard).set(*platforms.describe_tainacan(tainacan, docker))
        has = self.app.bridge.has_task("tainacan-status")
        self.query_one("#tainacan-install").display = has and platforms.tainacan_can_install(tainacan, docker)
        for key, _label in TAINACAN_BUTTONS[1:]:
            self.query_one(f"#tainacan-{key}").display = has and platforms.tainacan_installed(tainacan)
        await self._load_backups(platforms.tainacan_installed(tainacan))
        self.app.platforms_seen(status)

    async def _load_backups(self, installed: bool) -> None:
        """The "Platform backups" card: shown once a platform with backups
        is installed, or backups of one exist."""
        state = platforms.BackupState()
        if self.app.bridge.has_task("platform-backup-status"):
            try:
                out = await self.app.bridge.task("platform-backup-status", "tainacan")
                state = platforms.backup_from_results(out.results)
            except Exception:  # the card then says "not checked"
                state = platforms.BackupState()
        self.backup_state = state
        show = state.known and (installed or state.count > 0 or state.incomplete > 0)
        self.query_one("#platform-backups").display = show
        self.query_one("#platform-backups", StatusCard).set(*platforms.describe_backups(state))
        visible = {
            "setup": show and not state.key,
            "configure": show and bool(state.key),
            "kit": show and bool(state.key),
            "schedule": show and installed,
            "verify": show and state.count > 0 and installed,
            "incomplete": show and state.incomplete > 0,
        }
        for key, _label in BACKUP_BUTTONS:
            self.query_one(f"#pbackup-{key}").display = visible.get(key, False)

    async def install_docker(self) -> None:
        """The installer's plan, then the person's Yes, then the install."""
        from ..routines.common import run_task, show_done
        from ..screens.dialogs import ConfirmScreen, MessageScreen

        title = t("Install Docker")
        plan = await self.app.bridge.task("docker-plan")
        kind, note = plan.get("plan"), plan.get("note")
        if kind == "use":
            self.app.notify(note or t("Docker is already installed."))
            self.refresh_data()
            return
        if kind != "install":
            await self.app.push_screen_wait(MessageScreen(title, note or t("Docker cannot be installed here."),
                                                          kind="error"))
            return
        labels = (("repository", t("Repository")), ("key", t("Key")), ("source", t("Package source")),
                  ("packages", t("Packages")), ("service", t("Service")), ("kept", ""), ("firewall", ""),
                  ("undo", ""))
        steps = "\n".join(f"{label}: {plan.get(key)}" if label else plan.get(key)
                          for key, label in labels if plan.get(key))
        if not await self.app.push_screen_wait(ConfirmScreen(
                title, t("Install Docker now? No platform is installed with it."), preview=steps,
                preview_title=t("What will change on this server"))):
            return
        result = await run_task(self.app, title, "docker-install", "confirm")
        await show_done(self.app, title, result, t("Docker is installed."))
        self.refresh_data()

    async def remove_docker(self) -> None:
        """Only a Docker Koha.Nexus installed; the installer refuses while
        anything of anyone is in it."""
        from ..routines.common import run_task, show_done
        from ..screens.dialogs import ConfirmScreen

        title = t("Remove Docker")
        if not await self.app.push_screen_wait(ConfirmScreen(title, t(
                "Remove Docker, which Koha.Nexus installed? Nothing is left in it. "
                "Its images in /var/lib/docker are kept."), danger=True)):
            return
        result = await run_task(self.app, title, "docker-remove", "confirm")
        await show_done(self.app, title, result, t("Docker was removed."))
        self.refresh_data()

    def show(self, states: list[platforms.PlatformState]) -> None:
        for state in states:
            if state.id != "tainacan":     # its own card text (_load)
                self.query_one(f"#platform-{state.id}", StatusCard).set(*platforms.describe(state))

    # Tainacan: every action is a task of the installer, which checks
    # everything again (the buttons only follow --status-json).
    async def tainacan_install(self) -> None:
        """An address (or the server's own), the plan, a Yes, the install."""
        from ..routines.common import run_task, show_done
        from ..screens.dialogs import ConfirmScreen, InputScreen, MessageScreen

        title = t("Install Tainacan")

        def check(value: str) -> str:
            if not value or re.fullmatch(r"https?://[a-z0-9.-]+(:[0-9]{1,5})?/?", value):
                return ""
            return t("Use http://name or https://name, with no path, or leave it empty.")

        address = await self.app.push_screen_wait(InputScreen(
            title, t("Leave it empty to reach Tainacan by this server's address on the local network "
                     "(a port of its own). Or type the name it will have, such as http://acervo.example.org: "
                     "the name must point to this server."), t("Address (optional)"), validate=check))
        if address is None:
            return
        address = address.rstrip("/")
        plan = await self.app.bridge.task("tainacan-plan", *([address] if address else []))
        if plan.get("plan") != "install":
            await self.app.push_screen_wait(MessageScreen(
                title, plan.get("note") or t("Tainacan cannot be installed here."), kind="error"))
            return
        labels = (("address", t("Address")), ("web", t("Web")), ("apache", ""), ("images", t("Images")),
                  ("plugin", t("Plugin")), ("network", t("Network")), ("data", t("Data")), ("reuse", ""),
                  ("updates", ""), ("kept", ""), ("undo", ""))
        steps = "\n".join(f"{label}: {plan.get(key)}" if label else plan.get(key)
                          for key, label in labels if plan.get(key))
        if not await self.app.push_screen_wait(ConfirmScreen(
                title, t("Install Tainacan now? It takes a few minutes."), preview=steps,
                preview_title=t("What will change on this server"))):
            return
        args = ["confirm"] + ([plan.get("address")] if plan.get("address") else [])
        result = await run_task(self.app, title, "tainacan-install", *args)
        await show_done(self.app, title, result, t("Tainacan is installed."))
        self.refresh_data()

    async def tainacan_status(self) -> None:
        """The installer's diagnosis, as a list."""
        from ..screens.dialogs import TextScreen

        out = await self.app.bridge.task("tainacan-status")
        labels = (("status", t("Status")), ("url", t("Address")), ("health", t("Health")), ("reason", t("Reason")),
                  ("db", t("Database")), ("wordpress", "WordPress"), ("wordpress_version", t("WordPress version")),
                  ("tainacan_version", t("Tainacan version")), ("images_pinned", t("Images as fixed")),
                  ("collections", t("Collections")), ("items", t("Items")), ("attachments", t("Attachments")),
                  ("attachments_missing", t("Attachments missing on disk")), ("audit", t("Isolation rules")),
                  ("apache_site", t("Apache site")), ("last_backup", t("Last backup")), ("backups", t("Backups")),
                  ("disk_db", t("Database size")), ("disk_wp", t("Files size")), ("docker", "Docker"))
        text = "\n".join(f"{label}: {out.get(key)}" for key, label in labels if out.get(key))
        await self.app.push_screen_wait(TextScreen(t("Tainacan diagnosis"), text or t("Not checked")))

    async def tainacan_logs(self) -> None:
        from ..routines.common import run_task, show_done

        result = await run_task(self.app, t("Tainacan logs"), "tainacan-logs", "200")
        await show_done(self.app, t("Tainacan logs"), result)

    async def tainacan_backup(self) -> None:
        from ..routines.common import run_task, show_done

        title = t("Back up Tainacan")
        result = await run_task(self.app, title, "tainacan-backup")
        await show_done(self.app, title, result, t("The backup is ready."))
        self.refresh_data()

    async def _pick_backup(self, title: str) -> str | None:
        from ..screens.dialogs import ChoiceScreen, MessageScreen

        found: list[tuple[str, str]] = []

        def collect(key: str, value: str) -> None:
            if key == "backup":
                name, _sep, rest = value.partition("|")
                created, _sep, label = rest.partition("|")
                found.append((name, f"{created}  {label}  ({name})"))

        await self.app.bridge.task("tainacan-backups", on_result=collect)
        if not found:
            await self.app.push_screen_wait(MessageScreen(title, t("There is no complete Tainacan backup yet."),
                                                          kind="info"))
            return None
        return await self.app.push_screen_wait(ChoiceScreen(title, t("Which backup?"), found))

    async def tainacan_restore_test(self) -> None:
        from ..routines.common import run_task, show_done

        title = t("Test a restore")
        name = await self._pick_backup(title)
        if not name:
            return
        phrase = await self._ask_phrase(title)
        if phrase is None:
            return
        result = await run_task(self.app, title, "tainacan-restore-test", name, env=_phrase_env(phrase))
        await show_done(self.app, title, result)

    async def tainacan_restore(self) -> None:
        from ..routines.common import run_task, show_done
        from ..screens.dialogs import ConfirmScreen

        title = t("Restore Tainacan")
        name = await self._pick_backup(title)
        if not name:
            return
        if not await self.app.push_screen_wait(ConfirmScreen(title, t(
                "Restore this backup over the Tainacan in use? It is first tested in an isolated copy, and "
                "what is there now is saved in a safety backup; if the check fails, it goes back."),
                danger=True)):
            return
        phrase = await self._ask_phrase(title)
        if phrase is None:
            return
        result = await run_task(self.app, title, "tainacan-restore", name, env=_phrase_env(phrase))
        await show_done(self.app, title, result)
        self.refresh_data()

    async def _ask_phrase(self, title: str) -> str | None:
        """The recovery phrase, optional; None = cancelled. Without it the
        data is restored with this installation's configuration."""
        from ..screens.dialogs import InputScreen

        if not getattr(self, "backup_state", platforms.BackupState()).key:
            return ""
        return await self.app.push_screen_wait(InputScreen(
            title, t("The configuration in the backup (the keys of the WordPress sessions) is encrypted. Type the "
                     "recovery phrase to bring it back, or leave it empty: the data is restored and this "
                     "installation keeps its own configuration (people logged in must log in again)."),
            t("Recovery phrase (optional)"), password=True))

    # The platform backups (installer: kei_backup_*).
    async def backup_setup(self) -> None:
        """The plan, a phrase (typed, or a new one shown once), the key."""
        from ..routines.common import run_task, show_done
        from ..screens.dialogs import ConfirmScreen, InputScreen

        title = t("Set up encrypted backups")
        lines: list[str] = []

        def collect(key: str, value: str) -> None:
            if key == "package" and value:
                lines.append(f"{t('Package')}: {value}")
            elif key == "phrase" and value:
                lines.append(value)

        await self.app.bridge.task("platform-backup-plan", on_result=collect)
        preview = "\n".join(lines)
        if not await self.app.push_screen_wait(ConfirmScreen(
                title, t("Encrypt the configuration in the platform backups with a key of this server? Scheduled "
                         "backups need no phrase; restoring the configuration does."), preview=preview,
                preview_title=t("What will change on this server"))):
            return

        def check(value: str) -> str:
            return "" if not value or len(value) >= 12 else t("At least 12 characters, or leave it empty.")

        phrase = await self.app.push_screen_wait(InputScreen(
            title, t("Leave it empty and a recovery phrase is made and shown once: write it down and keep it away "
                     "from this server. Or type your own (12 characters or more)."),
            t("Recovery phrase (optional)"), validate=check, password=True))
        if phrase is None:
            return
        result = await run_task(self.app, title, "platform-backup-setup", "confirm", env=_phrase_env(phrase))
        await show_done(self.app, title, result, t("Encrypted backups are set up."))
        self.refresh_data()

    async def backup_configure(self) -> None:
        """Where the files go (a restic repository) and the cloud copy."""
        from ..routines.common import run_task, show_done
        from ..screens.dialogs import ChoiceScreen, InputScreen

        title = t("Repository and cloud copy")
        choice = await self.app.push_screen_wait(ChoiceScreen(title, t("What do you want to change?"), [
            ("repo-local", t("Files in a restic repository on this server")),
            ("repo-cloud", t("Files in a restic repository in the cloud (rclone)")),
            ("repo-none", t("Self-contained packages (no repository)")),
            ("copy", t("Copy each package to the cloud")),
            ("copy-none", t("Stop copying packages to the cloud"))]))
        if not choice:
            return

        def check(value: str) -> str:
            return "" if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}:[A-Za-z0-9_./-]*", value) and ".." not in value \
                else t("Use REMOTE:PATH, with a cloud connection of the panel.")

        target = ""
        if choice in ("repo-cloud", "copy"):
            target = await self.app.push_screen_wait(InputScreen(
                title, t("A cloud connection of the panel (Backups, Cloud) and a folder, such as gdrive:koha-nexus."),
                "REMOTE:PATH", validate=check))
            if not target:
                return
        task, value = {
            "repo-local": ("platform-backup-repo", "local"),
            "repo-cloud": ("platform-backup-repo", f"rclone:{target}"),
            "repo-none": ("platform-backup-repo", "none"),
            "copy": ("platform-backup-copy", target),
            "copy-none": ("platform-backup-copy", "none"),
        }[choice]
        result = await run_task(self.app, title, task, "tainacan", value)
        await show_done(self.app, title, result)
        self.refresh_data()

    async def backup_kit(self) -> None:
        from ..routines.common import failed, run_task, show_failure
        from ..screens.dialogs import MessageScreen

        title = t("Recovery kit")
        result = await run_task(self.app, title, "platform-backup-kit")
        if failed(result):
            await show_failure(self.app, title, result)
            return
        path = (result.value.last("ok", "info") or ("", "", ""))[2].strip().splitlines()[-1:] or [""]
        await self.app.push_screen_wait(MessageScreen(title, t(
            "The recovery kit was saved at ${path}. Copy it to a place away from this server (a pen drive, "
            "another computer). With the recovery phrase, which is not in it, a new server reads the "
            "encrypted backups and the restic repositories.", path=path[0]), kind="info"))

    async def backup_schedule(self) -> None:
        from ..routines.common import run_task, show_done
        from ..screens.dialogs import InputScreen

        title = t("Schedule backups")

        def check(value: str) -> str:
            return "" if value == "off" or re.fullmatch(r"([01][0-9]|2[0-3]):[0-5][0-9]", value) \
                else t("Use HH:MM (00:00 to 23:59) or off.")

        state = getattr(self, "backup_state", platforms.BackupState())
        value = await self.app.push_screen_wait(InputScreen(
            title, t("A daily backup at this time, maintenance on Sundays (retention, repository check) and a "
                     "restore test of a backup of about 30 days before on the 1st of each month. Type off to stop."),
            "HH:MM", validate=check, value=state.schedule or "02:30"))
        if not value:
            return
        result = await run_task(self.app, title, "platform-backup-schedule", "tainacan", value)
        await show_done(self.app, title, result)
        self.refresh_data()

    async def backup_verify(self) -> None:
        from ..routines.common import run_task, show_done

        title = t("Verify backups")
        result = await run_task(self.app, title, "platform-backup-verify", "tainacan", "30")
        await show_done(self.app, title, result)
        self.refresh_data()

    async def backup_incomplete(self) -> None:
        """An interrupted backup: resume it, or discard it."""
        from ..routines.common import run_task, show_done
        from ..screens.dialogs import ChoiceScreen, ConfirmScreen, MessageScreen

        title = t("Incomplete backup")
        found: list[tuple[str, str, str]] = []

        def collect(key: str, value: str) -> None:
            if key == "incomplete":
                name, _sep, rest = value.partition("|")
                last, _sep, restorable = rest.partition("|")
                found.append((name, last, restorable))

        await self.app.bridge.task("platform-backup-incomplete", "tainacan", on_result=collect)
        if not found:
            await self.app.push_screen_wait(MessageScreen(title, t("There is no incomplete backup."), kind="info"))
            self.refresh_data()
            return
        name = found[0][0] if len(found) == 1 else await self.app.push_screen_wait(ChoiceScreen(
            title, t("Which backup?"), [(n, f"{n}  ({t('stopped after')}: {last})") for n, last, _r in found]))
        if not name:
            return
        restorable = next((r for n, _l, r in found if n == name), "no") == "yes"
        options = [("resume", t("Resume it"))]
        if not restorable:
            options.append(("discard", t("Discard it")))
        action = await self.app.push_screen_wait(ChoiceScreen(title, t(
            "This backup stopped before the end. Resuming it does the capture again when it was cut, or goes "
            "on from the next step."), options))
        if action == "discard" and not await self.app.push_screen_wait(ConfirmScreen(
                title, t("Discard this incomplete backup?"), danger=True)):
            return
        if action not in ("resume", "discard"):
            return
        result = await run_task(self.app, title, f"platform-backup-{action}", name)
        await show_done(self.app, title, result)
        self.refresh_data()

    async def tainacan_credentials(self) -> None:
        from ..routines.common import run_task, show_done

        title = t("Tainacan administrator")
        result = await run_task(self.app, title, "tainacan-credentials")
        await show_done(self.app, title, result)

    async def tainacan_uninstall(self) -> None:
        from ..routines.common import run_task, show_done
        from ..screens.dialogs import ChoiceScreen, ConfirmScreen

        title = t("Uninstall Tainacan")
        choice = await self.app.push_screen_wait(ChoiceScreen(title, t("What happens to its data?"), [
            ("keep", t("Keep the data (installing it again uses it)")),
            ("delete", t("Delete the data (a last backup is made first)"))]))
        if choice not in ("keep", "delete"):
            return
        text = t("Uninstall Tainacan and keep its data?") if choice == "keep" else \
            t("Uninstall Tainacan and DELETE its collections, items and files? A last backup is made first "
              "and kept; nothing is deleted if it fails.")
        if not await self.app.push_screen_wait(ConfirmScreen(title, text, danger=choice == "delete")):
            return
        result = await run_task(self.app, title, "tainacan-uninstall", choice)
        await show_done(self.app, title, result)
        self.refresh_data()


# The Tainacan buttons, in order; the first shows while it is not
# installed, the others once it is.
TAINACAN_BUTTONS = (
    ("install", "Install Tainacan"),
    ("status", "Diagnosis"),
    ("logs", "Logs"),
    ("backup", "Back up now"),
    ("restore-test", "Test a restore"),
    ("restore", "Restore"),
    ("credentials", "Administrator"),
    ("uninstall", "Uninstall Tainacan"),
)


# The buttons of the "Platform backups" card.
BACKUP_BUTTONS = (
    ("setup", "Set up encrypted backups"),
    ("configure", "Repository and cloud copy"),
    ("kit", "Recovery kit"),
    ("schedule", "Schedule backups"),
    ("verify", "Verify now"),
    ("incomplete", "Incomplete backup"),
)


def _phrase_env(phrase: str) -> dict[str, str]:
    """The recovery phrase goes to the installer in its environment, never
    on its command line (where other users could read it)."""
    return {"KEI_BACKUP_PHRASE": phrase} if phrase else {}


class UnavailableView(SectionView):
    """Stands in for a section whose platform is not installed: a key or a
    link that leads there shows why, and nothing of it is loaded."""

    def __init__(self, section, reason: str):
        # Its own id ("view-<id>-off"): the real view keeps "view-<id>" for
        # when the platform is installed, so the two never collide.
        VerticalScroll.__init__(self, id=f"view-{section.id}-off", classes="view")
        self.section = section
        self.reason = reason

    def compose(self) -> ComposeResult:
        yield from self.heading()
        yield Label(self.reason, classes="view-prompt", id="unavailable-reason")
