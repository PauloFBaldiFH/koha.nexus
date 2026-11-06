"""Docker, Tainacan and the platform backups, as routines of the panel.

These flows used to live in the Platforms screen and in the Tainacan
section; they moved here unchanged when the panel was organized by
platform (menus.py: the Tainacan group, Shared infrastructure). Each one
is an async function (app) like every ported routine: its questions are
the panel's dialogs, its work is `config.sh --task`, which checks
everything again. A card only follows --status-json; nothing here starts,
stops, restores or removes anything without the plan and a Yes where the
installer asks for one. The recovery phrase goes to the installer in the
environment, never on its command line.

What a flow needs to know (is the backup key set up, which events
dependency is there) is read when it runs, never kept from a screen.
"""

from __future__ import annotations

import re

from .. import platforms
from ..i18n import t


async def _status(app) -> dict:
    try:
        status = await app.bridge.status()
    except Exception:  # the installer checks again; the flow goes on as before
        return {}
    return status if isinstance(status, dict) else {}


async def tainacan_state(app) -> platforms.TainacanState:
    return platforms.tainacan_from_status(await _status(app))


async def backup_state(app) -> platforms.BackupState:
    if not app.bridge.has_task("platform-backup-status"):
        return platforms.BackupState()
    try:
        out = await app.bridge.task("platform-backup-status", "tainacan")
    except Exception:  # then "not set up": the installer decides again
        return platforms.BackupState()
    return platforms.backup_from_results(out.results)


def _phrase_env(phrase: str) -> dict[str, str]:
    """The recovery phrase goes to the installer in its environment, never
    on its command line (where other users could read it)."""
    return {"KEI_BACKUP_PHRASE": phrase} if phrase else {}


async def install_docker(app, then: str = "") -> bool:
    """The installer's plan, then the person's Yes, then the install. True
    when Docker is there at the end. `then` = what comes after it (Tainacan's
    install), said in the question."""
    from .common import failed, run_task, show_done
    from ..screens.dialogs import ConfirmScreen, MessageScreen

    title = t("Install Docker")
    plan = await app.bridge.task("docker-plan")
    kind, note = plan.get("plan"), plan.get("note")
    if kind == "use":
        if not then:
            app.notify(note or t("Docker is already installed."))
        return True
    if kind != "install":
        await app.push_screen_wait(MessageScreen(title, note or t("Docker cannot be installed here."),
                                                      kind="error"))
        return False
    labels = (("repository", t("Repository")), ("key", t("Key")), ("source", t("Package source")),
              ("packages", t("Packages")), ("service", t("Service")), ("kept", ""), ("firewall", ""),
              ("undo", ""))
    steps = "\n".join(f"{label}: {plan.get(key)}" if label else plan.get(key)
                      for key, label in labels if plan.get(key))
    question = then or t("Install Docker now? No platform is installed with it.")
    if not await app.push_screen_wait(ConfirmScreen(
            title, question, preview=steps, preview_title=t("What will change on this server"))):
        return False
    result = await run_task(app, title, "docker-install", "confirm")
    if then and not failed(result):
        app.notify(t("Docker is installed."), timeout=5)
        return True
    await show_done(app, title, result, t("Docker is installed."))
    return not failed(result)


async def remove_docker(app) -> None:
    """Only a Docker Koha.Nexus installed; the installer refuses while
    anything of anyone is in it."""
    from .common import run_task, show_done
    from ..screens.dialogs import ConfirmScreen

    title = t("Remove Docker")
    if not await app.push_screen_wait(ConfirmScreen(title, t(
            "Remove Docker, which Koha.Nexus installed? Nothing is left in it. "
            "Its images in /var/lib/docker are kept."), danger=True)):
        return
    result = await run_task(app, title, "docker-remove", "confirm")
    await show_done(app, title, result, t("Docker was removed."))


async def tainacan_install(app) -> None:
    """An address (or the server's own), the plan, a Yes, the install."""
    from .common import run_task, show_done
    from ..screens.dialogs import ConfirmScreen, InputScreen, MessageScreen

    title = t("Install Tainacan")
    # Docker first, when it is missing: its own plan and Yes, then Tainacan
    # goes on here (no other screen to look for).
    docker = platforms.docker_from_status(await _status(app))
    if docker.known and not docker.installed:
        if not await app.push_screen_wait(ConfirmScreen(title, t(
                "Tainacan runs in containers and needs Docker, which is not installed on this server. First "
                "the plan to install Docker is shown; after it, the installation of Tainacan goes on. "
                "Go on?"))):
            return
        if not await install_docker(app, then=t(
                "Install Docker now? Nothing else is installed with it; Tainacan's own plan comes next.")):
            return
    elif docker.known and not docker.running:
        await app.push_screen_wait(MessageScreen(title, t(
            "Docker is installed but not running, so Tainacan cannot be installed now. See Shared "
            "infrastructure, or start Docker (systemctl start docker) and try again."), kind="error"))
        return

    def check(value: str) -> str:
        if not value or re.fullmatch(r"https?://[a-z0-9.-]+(:[0-9]{1,5})?/?", value):
            return ""
        return t("Use http://name or https://name, with no path, or leave it empty.")

    address = await app.push_screen_wait(InputScreen(
        title, t("Leave it empty to reach Tainacan by this server's address on the local network "
                 "(a port of its own). Or type the name it will have, such as http://acervo.example.org: "
                 "the name must point to this server."), t("Address (optional)"), validate=check))
    if address is None:
        return
    address = address.rstrip("/")
    plan = await app.bridge.task("tainacan-plan", *([address] if address else []))
    if plan.get("plan") != "install":
        await app.push_screen_wait(MessageScreen(
            title, plan.get("note") or t("Tainacan cannot be installed here."), kind="error"))
        return
    labels = (("address", t("Address")), ("web", t("Web")), ("apache", ""), ("images", t("Images")),
              ("plugin", t("Plugin")), ("network", t("Network")), ("data", t("Data")), ("reuse", ""),
              ("updates", ""), ("kept", ""), ("undo", ""))
    steps = "\n".join(f"{label}: {plan.get(key)}" if label else plan.get(key)
                      for key, label in labels if plan.get(key))
    if not await app.push_screen_wait(ConfirmScreen(
            title, t("Install Tainacan now? It takes a few minutes."), preview=steps,
            preview_title=t("What will change on this server"))):
        return
    args = ["confirm"] + ([plan.get("address")] if plan.get("address") else [])
    result = await run_task(app, title, "tainacan-install", *args)
    await show_done(app, title, result, t("Tainacan is installed."))


async def tainacan_backup(app) -> None:
    from .common import run_task, show_done

    title = t("Back up Tainacan")
    result = await run_task(app, title, "tainacan-backup")
    await show_done(app, title, result, t("The backup is ready."))


async def _pick_backup(app, title: str) -> str | None:
    from ..screens.dialogs import ChoiceScreen, MessageScreen

    found: list[tuple[str, str]] = []

    def collect(key: str, value: str) -> None:
        if key == "backup":
            name, _sep, rest = value.partition("|")
            created, _sep, label = rest.partition("|")
            found.append((name, f"{created}  {label}  ({name})"))

    await app.bridge.task("tainacan-backups", on_result=collect)
    if not found:
        await app.push_screen_wait(MessageScreen(title, t("There is no complete Tainacan backup yet."),
                                                      kind="info"))
        return None
    return await app.push_screen_wait(ChoiceScreen(title, t("Which backup?"), found))


async def tainacan_restore_test(app) -> None:
    from .common import run_task, show_done

    title = t("Test a restore")
    name = await _pick_backup(app, title)
    if not name:
        return
    phrase = await _ask_phrase(app, title)
    if phrase is None:
        return
    result = await run_task(app, title, "tainacan-restore-test", name, env=_phrase_env(phrase))
    await show_done(app, title, result)


async def tainacan_restore(app, name: str | None = None) -> None:
    """name: a package already chosen (the assisted restore: a folder, or a
    package extracted from a joint package); else one is picked here."""
    from .common import run_task, show_done
    from ..screens.dialogs import ConfirmScreen

    title = t("Restore Tainacan")
    name = name or await _pick_backup(app, title)
    if not name:
        return
    if not await app.push_screen_wait(ConfirmScreen(title, t(
            "Restore this backup over the Tainacan in use? It is first tested in an isolated copy, and "
            "what is there now is saved in a safety backup; if the check fails, it goes back."),
            danger=True)):
        return
    phrase = await _ask_phrase(app, title)
    if phrase is None:
        return
    if not phrase and not await _events_restore_note(app, title, name):
        return
    result = await run_task(app, title, "tainacan-restore", name, env=_phrase_env(phrase))
    await show_done(app, title, result)


async def _events_restore_note(app, title: str, name: str) -> bool:
    """Without the phrase, the event pass links already sent stop working
    when the backup was signed with other keys: said before the restore,
    which goes on only after a Yes. True = go on."""
    from ..screens.dialogs import ConfirmScreen

    if not app.bridge.has_task("tainacan-restore-notes"):
        return True
    notes: list[str] = []
    try:
        await app.bridge.task("tainacan-restore-notes", name, "nophrase",
                                   on_result=lambda k, v: notes.append(v) if k == "note" and v else None)
    except Exception:  # the installer says it again at the end of the restore
        return True
    if not notes:
        return True
    return bool(await app.push_screen_wait(ConfirmScreen(
        title, "\n".join(notes) + "\n\n" + t("Restore without the recovery phrase anyway?"), danger=True)))


async def _ask_phrase(app, title: str) -> str | None:
    """The recovery phrase, optional; None = cancelled. Without it the
    data is restored with this installation's configuration."""
    from ..screens.dialogs import InputScreen

    if not (await backup_state(app)).key:
        return ""
    return await app.push_screen_wait(InputScreen(
        title, t("The configuration in the backup (the keys of the WordPress sessions) is encrypted. Type the "
                 "recovery phrase to bring it back, or leave it empty: the data is restored and this "
                 "installation keeps its own configuration (people logged in must log in again)."),
        t("Recovery phrase (optional)"), password=True, validate=lambda _value: ""))

# The platform backups (installer: kei_backup_*).


async def backup_setup(app) -> None:
    """The plan, a phrase (typed, or a new one shown once), the key."""
    from .common import run_task, show_done
    from ..screens.dialogs import ConfirmScreen, InputScreen

    title = t("Set up encrypted backups")
    lines: list[str] = []

    def collect(key: str, value: str) -> None:
        if key == "package" and value:
            lines.append(f"{t('Package')}: {value}")
        elif key == "phrase" and value:
            lines.append(value)

    await app.bridge.task("platform-backup-plan", on_result=collect)
    preview = "\n".join(lines)
    if not await app.push_screen_wait(ConfirmScreen(
            title, t("Encrypt the configuration in the platform backups with a key of this server? Scheduled "
                     "backups need no phrase; restoring the configuration does."), preview=preview,
            preview_title=t("What will change on this server"))):
        return

    def check(value: str) -> str:
        return "" if not value or len(value) >= 12 else t("At least 12 characters, or leave it empty.")

    phrase = await app.push_screen_wait(InputScreen(
        title, t("Leave it empty and a recovery phrase is made and shown once: write it down and keep it away "
                 "from this server. Or type your own (12 characters or more)."),
        t("Recovery phrase (optional)"), validate=check, password=True))
    if phrase is None:
        return
    result = await run_task(app, title, "platform-backup-setup", "confirm", env=_phrase_env(phrase))
    await show_done(app, title, result, t("Encrypted backups are set up."))


async def backup_configure(app) -> None:
    """Where the files go (a restic repository) and the cloud copy."""
    from .common import run_task, show_done
    from ..screens.dialogs import ChoiceScreen, InputScreen

    title = t("Repository and cloud copy")
    choice = await app.push_screen_wait(ChoiceScreen(title, t("What do you want to change?"), [
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
        target = await app.push_screen_wait(InputScreen(
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
    result = await run_task(app, title, task, "tainacan", value)
    await show_done(app, title, result)


async def backup_kit(app) -> None:
    from .common import failed, run_task, show_failure
    from ..screens.dialogs import MessageScreen

    title = t("Recovery kit")
    result = await run_task(app, title, "platform-backup-kit")
    if failed(result):
        await show_failure(app, title, result)
        return
    path = (result.value.last("ok", "info") or ("", "", ""))[2].strip().splitlines()[-1:] or [""]
    await app.push_screen_wait(MessageScreen(title, t(
        "The recovery kit was saved at ${path}. Copy it to a place away from this server (a pen drive, "
        "another computer). With the recovery phrase, which is not in it, a new server reads the "
        "encrypted backups and the restic repositories.", path=path[0]), kind="info"))


async def backup_schedule(app) -> None:
    from .common import run_task, show_done
    from ..screens.dialogs import InputScreen

    title = t("Schedule backups")

    def check(value: str) -> str:
        return "" if value == "off" or re.fullmatch(r"([01][0-9]|2[0-3]):[0-5][0-9]", value) \
            else t("Use HH:MM (00:00 to 23:59) or off.")

    state = await backup_state(app)
    value = await app.push_screen_wait(InputScreen(
        title, t("A daily backup at this time, maintenance on Sundays (retention, repository check) and a "
                 "restore test of a backup of about 30 days before on the 1st of each month. Type off to stop."),
        "HH:MM", validate=check, value=state.schedule or "02:30"))
    if not value:
        return
    result = await run_task(app, title, "platform-backup-schedule", "tainacan", value)
    await show_done(app, title, result)


async def backup_verify(app) -> None:
    from .common import run_task, show_done

    title = t("Verify backups")
    result = await run_task(app, title, "platform-backup-verify", "tainacan", "30")
    await show_done(app, title, result)


async def backup_incomplete(app) -> None:
    """An interrupted backup: resume it, or discard it."""
    from .common import run_task, show_done
    from ..screens.dialogs import ChoiceScreen, ConfirmScreen, MessageScreen

    title = t("Incomplete backup")
    found: list[tuple[str, str, str]] = []

    def collect(key: str, value: str) -> None:
        if key == "incomplete":
            name, _sep, rest = value.partition("|")
            last, _sep, restorable = rest.partition("|")
            found.append((name, last, restorable))

    await app.bridge.task("platform-backup-incomplete", "tainacan", on_result=collect)
    if not found:
        await app.push_screen_wait(MessageScreen(title, t("There is no incomplete backup."), kind="info"))
        return
    name = found[0][0] if len(found) == 1 else await app.push_screen_wait(ChoiceScreen(
        title, t("Which backup?"), [(n, f"{n}  ({t('stopped after')}: {last})") for n, last, _r in found]))
    if not name:
        return
    restorable = next((r for n, _l, r in found if n == name), "no") == "yes"
    options = [("resume", t("Resume it"))]
    if not restorable:
        options.append(("discard", t("Discard it")))
    action = await app.push_screen_wait(ChoiceScreen(title, t(
        "This backup stopped before the end. Resuming it does the capture again when it was cut, or goes "
        "on from the next step."), options))
    if action == "discard" and not await app.push_screen_wait(ConfirmScreen(
            title, t("Discard this incomplete backup?"), danger=True)):
        return
    if action not in ("resume", "discard"):
        return
    result = await run_task(app, title, f"platform-backup-{action}", name)
    await show_done(app, title, result)


async def tainacan_uninstall(app) -> None:
    from .common import run_task, show_done
    from ..screens.dialogs import ChoiceScreen, ConfirmScreen

    title = t("Uninstall Tainacan")
    choice = await app.push_screen_wait(ChoiceScreen(title, t("What happens to its data?"), [
        ("keep", t("Keep the data (installing it again uses it)")),
        ("delete", t("Delete the data (a last backup is made first)"))]))
    if choice not in ("keep", "delete"):
        return
    text = t("Uninstall Tainacan and keep its data?") if choice == "keep" else \
        t("Uninstall Tainacan and DELETE its collections, items and files? A last backup is made first "
          "and kept; nothing is deleted if it fails.")
    if not await app.push_screen_wait(ConfirmScreen(title, text, danger=choice == "delete")):
        return
    result = await run_task(app, title, "tainacan-uninstall", choice)
    await show_done(app, title, result)


async def tainacan_status(app) -> None:
    """The installer's full diagnosis, as a list. The installer keeps it
    (with the time it was read) for the summary; a failed read keeps
    the one before and says why."""
    from ..screens.dialogs import MessageScreen, TextScreen

    out = await app.bridge.task("tainacan-status")
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
        await app.push_screen_wait(MessageScreen(
            t("Tainacan diagnosis"), f"{msg[2]}\n\n{keep}" if msg and msg[2] else
            t("The diagnosis could not be read.") + "\n\n" + keep, kind="error"))
        return
    text = "\n".join(f"{label}: {out.get(key)}" for key, label in labels if out.get(key))
    checked = out.get("checked_at")
    if checked.isdigit():
        text += "\n\n" + t("Read at ${when}.", when=platforms.when(int(checked)))
    await app.push_screen_wait(TextScreen(t("Tainacan diagnosis"), text or t("Not checked")))


async def tainacan_logs(app) -> None:
    from .common import run_task, show_done

    result = await run_task(app, t("Tainacan logs"), "tainacan-logs", "200")
    await show_done(app, t("Tainacan logs"), result)


async def tainacan_credentials(app) -> None:
    from .common import run_task, show_done

    title = t("Tainacan administrator")
    result = await run_task(app, title, "tainacan-credentials")
    await show_done(app, title, result)



def _plan_steps(plan, labels) -> str:
    return "\n".join(f"{label}: {plan.get(key)}" if label else plan.get(key)
                     for key, label in labels if plan.get(key))


async def tainacan_start(app) -> None:
    """A stopped Tainacan: Docker and its two containers started again, the
    data as it is. The plan first, then the person's Yes; never a restore."""
    from .common import run_task, show_done
    from ..screens.dialogs import ConfirmScreen, MessageScreen

    title = t("Start Tainacan")
    plan = await app.bridge.task("tainacan-start")
    kind, note = plan.get("plan"), plan.get("note")
    if kind == "ready":
        await app.push_screen_wait(MessageScreen(title, note or t("The Tainacan containers are already running.")))
        return
    if kind != "start":
        await app.push_screen_wait(MessageScreen(title, note or t("Tainacan cannot be started here."), kind="error"))
        return
    steps = _plan_steps(plan, (("docker", ""), ("containers", ""), ("start", ""), ("check", "")))
    if not await app.push_screen_wait(ConfirmScreen(title, t("Start Tainacan now?"), preview=steps,
                                                    preview_title=t("What will change on this server"))):
        return
    result = await run_task(app, title, "tainacan-start", "confirm")
    await show_done(app, title, result, t("Tainacan is running again, with its data as it was."))
    app.check_platforms()


async def tainacan_site(app) -> None:
    """The public home page of the collection: the installer's plan (what
    changes, what stays), the person's Yes, then the change. Nothing of the
    site is deleted; undo puts it back."""
    from .common import run_task, show_done
    from ..screens.dialogs import ConfirmScreen, MessageScreen

    title = t("Prepare the home page")
    plan = await app.bridge.task("tainacan-site", "plan")
    kind, note = plan.get("plan"), plan.get("note")
    if kind == "ready":
        await app.push_screen_wait(MessageScreen(title, note or t("The home page of the collection is already prepared.")))
        return
    if kind != "apply":
        await app.push_screen_wait(MessageScreen(title, note or t("The home page cannot be prepared here."),
                                                 kind="error"))
        return
    steps = _plan_steps(plan, (("page", ""), ("front", ""), ("posts", ""), ("facets", ""), ("kept", ""), ("undo", "")))
    if not await app.push_screen_wait(ConfirmScreen(
            title, t("Prepare the public home page of the collection now?"), preview=steps,
            preview_title=t("What will change in WordPress"))):
        return
    result = await run_task(app, title, "tainacan-site", "apply", "confirm")
    await show_done(app, title, result, t("The home page of the collection is ready."))
    app.check_platforms()


async def tainacan_site_undo(app) -> None:
    from .common import run_task, show_done
    from ..screens.dialogs import ConfirmScreen

    title = t("Undo the home page")
    if not await app.push_screen_wait(ConfirmScreen(title, t(
            "Put back the home page and settings that were there before? The page of the collection goes to "
            "the trash if nobody edited it; an edited one is kept. Tainacan's collections and items do not "
            "change."))):
        return
    result = await run_task(app, title, "tainacan-site", "undo", "confirm")
    await show_done(app, title, result, t("The previous home page and settings are back."))
    app.check_platforms()

# Events in Tainacan (installer: --task tainacan-events). Off until the
# person turns them on; every step is the installer's, which checks
# again what the buttons only follow.


async def events_on(app) -> None:
    """The installer's plan, then the person's Yes, then events on."""
    from .common import run_task, show_done
    from ..screens.dialogs import ConfirmScreen, MessageScreen

    title = t("Turn events on")
    plan = await app.bridge.task("tainacan-events", "plan")
    if plan.get("plan") != "enable":
        await app.push_screen_wait(MessageScreen(
            title, plan.get("note") or t("Events cannot be turned on now."), kind="error"))
        return
    labels = (("dependency", "Events Manager"), ("plugin", "Nexus Eventos"), ("data", t("Data")),
              ("undo", ""))
    steps = "\n".join(f"{label}: {plan.get(key)}" if label else plan.get(key)
                      for key, label in labels if plan.get(key))
    if not await app.push_screen_wait(ConfirmScreen(
            title, t("Turn events on in Tainacan? Its collections and items do not change."), preview=steps,
            preview_title=t("What will change on this server"))):
        return
    result = await run_task(app, title, "tainacan-events", "enable", "confirm")
    if result.cancelled:
        await app.push_screen_wait(MessageScreen(title, t(
            "Turning events on was stopped before the end, so events stay off. What was already put in is "
            "kept and used when you turn events on again."), kind="info"))
    else:
        await show_done(app, title, result, t("Events are on."))


async def events_off(app) -> None:
    """Events off, their data kept. Events Manager: the person decides,
    and one that was there before stays on by default."""
    from .common import run_task, show_done
    from ..screens.dialogs import ChoiceScreen, ConfirmScreen

    title = t("Turn events off")
    state = await tainacan_state(app)
    how = await app.push_screen_wait(ChoiceScreen(
        title, t("Events, bookings, attendance and certificates are kept: turning events on again brings "
                 "them back. What happens to Events Manager?"), platforms.events_off_choices(state)))
    if how not in ("default", "keep-dependency", "dependency"):
        return
    if how == "dependency":
        question = t("Turn events off and also turn off Events Manager, which was in this WordPress before "
                     "Koha.Nexus? Whatever else uses it in this site stops too. No data is deleted.")
    else:
        question = t("Turn events off? No data is deleted.")
    if not await app.push_screen_wait(ConfirmScreen(title, question, danger=how == "dependency")):
        return
    result = await run_task(app, title, "tainacan-events", "disable",
                            *([] if how == "default" else [how]))
    await show_done(app, title, result, t("Events are off. Their data was kept."))


async def events_status(app) -> None:
    """The installer's view of events: on or off, both plugins, the data."""
    from ..screens.dialogs import TextScreen

    out = await app.bridge.task("tainacan-events", "status")
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
    await app.push_screen_wait(TextScreen(t("Events in Tainacan"), "\n".join(lines)))


