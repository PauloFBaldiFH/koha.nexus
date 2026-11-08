"""The joint package (Koha + Tainacan) and the assisted restore, in the
Backup center (Paulo, 2026-11-06). The installer does the work
(kei_set_backup, kei_set_inspect, kei_set_unpack, kei_set_cleanup); the
restores themselves are the routines that already existed: Koha's
"Restore database" (restore-check, its safety backup) and "Restore
Tainacan" (the test in an isolated copy, its safety backup, the recovery
phrase), so their confirmations are kept.

Koha's files (uploads, plugins, images, the panel's rules) and its
secrets (the encryption key in koha-conf.xml, SIP2 and the panel's
logins) go in the set; the secrets only encrypted with the backup key.
Without the key the person chooses first: set it up, or a package of data
only, never called complete. After the database, the restore offers
Koha's files and secrets with a plan: only <encryption_key> of
koha-conf.xml comes back; the target keeps its database password, paths
and its own secret files (the packaged ones are saved beside them). No
value is ever shown (document V).

A file is recognised by its content, never its name. Nothing a manifest
says is run: it is only read and shown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..bridge import TaskOutcome
from ..i18n import t
from ..screens.dialogs import ChoiceScreen, ConfirmScreen, InputScreen, MessageScreen
from ..screens.files import PathPickerScreen
from .common import facts, run_task, show_failure

NAMES = {"koha": "Koha", "tainacan": "Tainacan", "dspace": "DSpace"}


@dataclass
class Part:
    """One platform of a set: its capture, as the set's manifest says."""
    id: str
    ok: bool
    started: str = ""
    finished: str = ""
    secrets: str = ""
    error: str = ""
    recov: str = ""                # full | data-only | none ("" = an older installer)


@dataclass
class Inspected:
    """What kei_set_inspect said about a file."""
    kind: str = "unknown"          # koha-sql | koha-nexus-set | tainacan-package | tainacan-archive | unsafe | unknown
    why: str = ""
    created: str = ""
    host: str = ""
    version: str = ""
    complete: bool = True
    integrity: str = ""
    platforms: list[str] = field(default_factory=list)
    parts: list[Part] = field(default_factory=list)
    conflicts: dict[str, str] = field(default_factory=dict)
    recoverability: str = ""       # full | partial ("" = an older installer)
    koha_files: bool = False


def parse_inspect(out: TaskOutcome) -> Inspected:
    r = out.results
    info = Inspected(kind=r.get("kind", "unknown"), why=r.get("why", ""), created=r.get("created", ""),
                     host=r.get("host", ""), version=r.get("panel_version", ""),
                     complete=r.get("complete", "yes") != "no", integrity=r.get("integrity", ""),
                     platforms=[p for p in r.get("platforms", "").split() if p in NAMES],
                     recoverability=r.get("recoverability", ""), koha_files=r.get("koha_files") == "yes")
    for line in out.lists.get("part", []):
        cols = (line.split("\t") + [""] * 7)[:7]
        if cols[0] in NAMES:
            info.parts.append(Part(cols[0], cols[1] == "ok", cols[2], cols[3], cols[4], cols[5], cols[6]))
    for line in out.lists.get("conflict", []):
        pid, _sep, text = line.partition("\t")
        if pid in NAMES:
            info.conflicts[pid] = text
    return info


def parse_backup(out: TaskOutcome) -> list[Part]:
    """The platform lines of set-backup: ID, ok|failed, start, end, path or
    why, recoverability."""
    parts = []
    for line in out.lists.get("platform", []):
        cols = (line.split("\t") + [""] * 6)[:6]
        if cols[0] in NAMES:
            ok = cols[1] == "ok"
            parts.append(Part(cols[0], ok, cols[2], cols[3], error="" if ok else cols[4], recov=cols[5]))
    return parts


def secrets_text(part: Part) -> str:
    """What of a part is encrypted: never "encrypted" for the whole."""
    if part.id == "koha":
        if part.secrets == "gpg":
            return t("its files, and its secrets (encryption key, SIP2 and panel logins) encrypted with the backup key")
        return t("database and files, WITHOUT its secrets: what Koha encrypted (staff two-factor secrets) "
                 "cannot be read on another installation")
    if part.id == 'dspace':
        return t('Entire PostgreSQL, configuration, files and Solr package encrypted with the backup key')
    return t("configuration encrypted with the backup key") if part.secrets == "gpg" \
        else t("configuration not encrypted (readable by root only)")


def recoverability_text(full: bool) -> str:
    """Never "complete" for a package without the secrets; and what is never in any package."""
    head = t("Recoverable in full with the recovery phrase.") if full else t(
        "NOT recoverable in full: a part of it has the data without its secrets.")
    return head + " " + t("Never in the package (outside it): the Koha program (koha-common), the cloud "
                          "accounts, the Cloudflare tunnel or free address; the search index is rebuilt from the "
                          "database.")


def summary(info: Inspected) -> str:
    """Origin, date, platforms, integrity, each capture and the conflicts."""
    lines = [t("Joint package of Koha.Nexus") if info.kind == "koha-nexus-set" else t("Tainacan package")]
    if info.host:
        lines.append(t("Made on: ${host}", host=info.host) + (f" · {info.version}" if info.version else ""))
    if info.created:
        lines.append(t("Date: ${date}", date=info.created))
    integrity = {"ok": t("✅ every file matches its checksum"), "failed": t("⚠ the files do not match their checksums"),
                 "unchecked": t("checked when it is extracted")}.get(info.integrity, info.integrity)
    lines.append(t("Integrity: ${state}", state=integrity))
    if not info.complete:
        lines.append(t("⚠ Incomplete set: a platform failed when it was made."))
    for part in info.parts:
        name = NAMES[part.id]
        if part.ok:
            when = f"{part.started} → {part.finished}" if part.finished else part.started
            lines.append(f"• {name}: {t('captured')} {when}; {secrets_text(part)}")
        else:
            lines.append(f"• {name}: {t('not in the set')} ({part.error or t('failed')})")
    if info.kind == "koha-nexus-set":
        lines.append(t("Each platform was captured in turn, with its own consistent copy: not at the same instant."))
        if info.recoverability:
            lines.append(recoverability_text(info.recoverability == "full"))
    for pid, text in info.conflicts.items():
        lines.append(f"{NAMES[pid]}: {text}")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Joint backup
# ----------------------------------------------------------------------
async def set_backup(app) -> None:
    from ..backup_center import MEMBERS
    selected = list(MEMBERS.get(getattr(app, 'backup_scope', 'both'), ('koha','tainacan')))
    title = t("Joint backup") + ' · ' + ' + '.join(NAMES[p] for p in selected)
    info = await facts(app)
    home = info.get("real_home") or "/root"
    start = Path(home) / "backups"
    try:
        usable = start.is_dir()
    except OSError:          # a home this user cannot read (not root)
        usable = False
    folder = await app.push_screen_wait(PathPickerScreen(
        title, start if usable else home, mode="dir",
        help_text=t("Choose the folder of this server where the joint package is saved.")))
    if folder is None:
        return
    mode = await _secrets_choice(app, title, selected)
    if mode is None:
        return
    if not await app.push_screen_wait(ConfirmScreen(title, t(
            "One file with the data of the selected platforms, and a manifest with the checksums. Each platform "
            "is captured in turn with its own consistent copy (Tainacan stops writing for a moment), and the "
            "time of each capture is recorded: the two are not taken at the same instant. Make it now?"))):
        return
    args = (("",mode) if mode else ()) if selected == ['koha','tainacan'] else (','.join(selected),mode)
    result = await run_task(app, title, "set-backup", str(folder), *args)
    out = result.value if isinstance(result.value, TaskOutcome) else None
    parts = parse_backup(out) if out else []
    file = out.results.get("file", "") if out else ""
    if out and out.results.get("needs") == "key":
        await app.push_screen_wait(MessageScreen(title, t(
            "Nothing was made: Koha's secrets need the backup key. Set it up in the Backup center, or make the "
            "joint backup again and choose a package without the secrets."), kind="error"))
        return
    if result.cancelled or not file:
        await show_failure(app, title, result)
        return
    lines = []
    for part in parts:
        mark = "✅" if part.ok else "⚠"
        what = f"{part.started} → {part.finished}" if part.ok else part.error
        if part.ok and part.recov == "data-only":
            what += " · " + t("data without its secrets")
        lines.append(f"{mark} {NAMES[part.id]}: {what}")
    full = out.results.get("recoverability", "full") == "full"
    body = "\n".join(lines) + "\n\n" + recoverability_text(full) + "\n\n" + t("File: ${file}", file=file)
    if out.results.get("complete") == "yes":
        head = t("✅ Joint backup done.") if full else t("✅ Joint backup done, with data only for the platform "
                                                       "marked: not a complete recovery.")
        await app.push_screen_wait(MessageScreen(title, head + "\n\n" + body, kind="ok"))
    else:
        await app.push_screen_wait(MessageScreen(title, t(
            "⚠ The joint backup is NOT complete: the platform marked ⚠ below is not in it. The part that worked is "
            "in the file (named -partial). Fix the cause shown next to it and make the joint backup again; each "
            "platform can also be backed up on its own in the Backup center.") + "\n\n" + body, kind="error"))


async def _secrets_choice(app, title: str, selected=None) -> str | None:
    """"" = with the secrets, "no-secrets" = the person chose data only,
    None = cancelled. Asked only when Koha is here and there is no backup
    key: its secrets are never left out in silence, and never go in clear."""
    from . import platforms as tn

    if selected and 'dspace' in selected:
        if not (await tn.backup_state(app)).key:
            if not await app.push_screen_wait(ConfirmScreen(title,t('DSpace backups require encryption. Configure the shared backup key now?'))):return None
            await tn.backup_setup(app)
            if not (await tn.backup_state(app)).key:return None
        return ""
    if not app.platform_ready("koha") or (selected and 'koha' not in selected):
        return ""
    if (await tn.backup_state(app)).key:
        return ""
    choice = await app.push_screen_wait(ChoiceScreen(title, t(
        "There is no backup key on this server, so Koha's secrets (its encryption key in koha-conf.xml, the "
        "SIP2 logins and the panel's logins) cannot go into the package: they never go in clear. Without them "
        "the package has the data only: what Koha encrypted (staff two-factor secrets, other stored passwords) "
        "cannot be read on another installation, and the package is marked as data only, not complete."), [
        ("key", t("Set up the backup key now (recommended)")),
        ("data", t("Make the package without Koha's secrets (data only)"))]))
    if choice is None:
        return None
    if choice == "data":
        return "no-secrets"
    await tn.backup_setup(app)
    if (await tn.backup_state(app)).key:
        return ""
    return None


# ----------------------------------------------------------------------
# The scheduled joint backup (installer: kei_set_schedule, kei_set_run)
# ----------------------------------------------------------------------
async def set_schedule(app) -> None:
    """The same joint backup every day: its folder, the sets kept, an
    encrypted cloud copy. Written only here, never by an update."""
    import re

    from . import platforms as tn
    from ..screens.dialogs import InputScreen
    from .common import show_done

    title = t("⏰  Schedule the joint backup")
    if not app.bridge.has_task("set-schedule"):
        await app.push_screen_wait(MessageScreen(title, t(
            "The installer on this server is older than the panel: update it to schedule the joint backup."),
            kind="error"))
        return
    try:
        status = dict((await app.bridge.task("set-schedule-status")).results)
    except Exception:  # noqa: BLE001 - then as if nothing was scheduled
        status = {}
    if status.get("schedule"):
        what = await app.push_screen_wait(ChoiceScreen(title, t(
            "The joint backup runs every day at ${time} in ${dest}; the newest ${keep} sets are kept.",
            time=status["schedule"], dest=status.get("dest", ""), keep=status.get("keep", "")), [
            ("change", t("Change the schedule")), ("off", t("Turn the scheduled joint backup off"))]))
        if what is None:
            return
        if what == "off":
            if not await app.push_screen_wait(ConfirmScreen(title, t(
                    "Turn the scheduled joint backup off? The sets already made are kept."))):
                return
            result = await run_task(app, title, "set-schedule", "time=off")
            await show_done(app, title, result)
            return
    mode = await _secrets_choice(app, title)
    if mode is None:
        return
    has_key = bool((await tn.backup_state(app)).key)
    info = await facts(app)
    home = info.get("real_home") or "/root"
    start = Path(status.get("dest") or Path(home) / "backups")
    try:
        usable = start.is_dir()
    except OSError:          # a folder this user cannot read (not root)
        usable = False
    folder = await app.push_screen_wait(PathPickerScreen(
        title, start if usable else home, mode="dir",
        help_text=t("Choose the folder of this server where the scheduled joint packages are saved.")))
    if folder is None:
        return

    def check_time(value: str) -> str:
        return "" if re.fullmatch(r"([01][0-9]|2[0-3]):[0-5][0-9]", value) else t("Use HH:MM (00:00 to 23:59).")

    when = await app.push_screen_wait(InputScreen(title, t(
        "At what time, every day? Choose a time when the library is closed: Tainacan stops writing for a "
        "moment while it is captured."), "HH:MM", validate=check_time, value=status.get("schedule") or "01:30"))
    if not when:
        return

    def check_keep(value: str) -> str:
        return "" if value.isdigit() and 1 <= int(value) <= 365 else t("From 1 to 365.")

    keep = await app.push_screen_wait(InputScreen(title, t(
        "How many complete sets to keep in that folder? Older ones made by this schedule are removed after a "
        "complete set; sets made by hand are never removed."), t("Sets kept"), validate=check_keep,
        value=status.get("keep") or "7"))
    if not keep:
        return
    copy = "none"
    if has_key:
        def check_copy(value: str) -> str:
            return "" if not value or (re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}:[A-Za-z0-9_./-]*", value)
                                       and ".." not in value) \
                else t("Use REMOTE:PATH, with a cloud connection of the panel.")

        typed = await app.push_screen_wait(InputScreen(title, t(
            "Also copy each set to the cloud? It goes whole, encrypted with the backup key (.tar.gpg). Type a "
            "cloud connection of the panel and a folder (such as gdrive:koha-nexus-sets), or leave it empty."),
            "REMOTE:PATH", validate=check_copy, value=status.get("copy", "")))
        if typed is None:
            return
        copy = typed or "none"
    lines = [t("Every day at ${time}", time=when), t("Folder: ${dest}", dest=str(folder)),
             t("The newest ${n} sets kept", n=keep),
             t("Cloud copy: ${copy}", copy=copy) if copy != "none" else t("No cloud copy"),
             t("Koha without its secrets (data only)") if mode else t("Koha's secrets encrypted with the backup key")]
    if not await app.push_screen_wait(ConfirmScreen(title, t(
            "The same joint backup as by hand, on a schedule: each platform in turn, a line in its history, "
            "never two at the same time.") + "\n\n" + "\n".join("• " + line for line in lines)
            + "\n\n" + t("Schedule it?"))):
        return
    result = await run_task(app, title, "set-schedule", f"time={when}", f"dest={folder}", f"keep={keep}",
                            f"copy={copy}", "secrets=no" if mode else "secrets=yes")
    await show_done(app, title, result)


# ----------------------------------------------------------------------
# Assisted restore
# ----------------------------------------------------------------------
async def restore_assisted(app) -> None:
    title = t("♻  Assisted restore")
    info = await facts(app)
    home = info.get("real_home") or "/root"
    where = await app.push_screen_wait(ChoiceScreen(title, t(
        "Which backup? It is recognised by its content, not by its name: a Koha database backup (any "
        "version), a Tainacan package or a joint package of Koha.Nexus."), [
        ("file", t("A file (Koha backup, joint package or Tainacan package archive)")),
        ("folder", t("A Tainacan package folder"))]))
    if where is None:
        return
    picked = await app.push_screen_wait(PathPickerScreen(
        title, home, mode="file" if where == "file" else "dir", suffixes=() if where == "file" else None))
    if picked is None:
        return
    path = str(picked)
    result = await run_task(app, t("Checking the backup"), "set-inspect", path)
    out = result.value if isinstance(result.value, TaskOutcome) else None
    if out is None or result.cancelled or not out.ok:
        await show_failure(app, title, result)
        return
    found = parse_inspect(out)
    if found.kind == "koha-sql":
        from . import backup
        await backup.restore(app, path)          # restore-check, the safety backup, its own questions
        return
    if found.kind == 'unknown' and where == 'file':
        encrypted=await app.push_screen_wait(ChoiceScreen(title,t('This file may be encrypted. Choose its recovery type; the contents will still be verified before any restoration.'),[('set',t('Encrypted platform set')),('dspace',t('Encrypted DSpace package'))]))
        if encrypted=='dspace':
            from . import dspace
            await dspace.restore_path(app,path)
            return
        if encrypted=='set':
            phrase=await app.push_screen_wait(InputScreen(title,t('Recovery phrase for the encrypted set:'),t('Recovery phrase:'),password=True))
            if not phrase:return
            opened=await run_task(app,title,'set-open',path,env={'KEI_BACKUP_PHRASE':phrase})
            opened_out=opened.value if isinstance(opened.value,TaskOutcome) else None
            if not opened_out or not opened_out.ok or not opened_out.results.get('opened'):
                await show_failure(app,title,opened);return
            try:
                inspect=await app.bridge.task('set-inspect',opened_out.results['opened'])
                await _restore_parts(app,title,opened_out.results['opened'],parse_inspect(inspect))
            finally:
                await app.bridge.task('set-cleanup',opened_out.results['stage'])
            return
        return
    if found.kind in ("unsafe", "unknown"):
        body = t("This file was refused before anything was extracted: ${why}. Nothing was changed.",
                 why=found.why or t("unsafe content")) if found.kind == "unsafe" else t(
            "This is not a backup this panel knows. Koha database backups (.sql, .sql.gz, .sql.zst, .sql.xz), "
            "Tainacan packages and joint packages of Koha.Nexus are recognised by their content.")
        await app.push_screen_wait(MessageScreen(title, body, kind="error"))
        return
    if found.integrity == "failed":
        await app.push_screen_wait(MessageScreen(title, summary(found) + "\n\n" + t(
            "It cannot be restored: a damaged or changed backup is never applied."), kind="error"))
        return
    await _restore_parts(app, title, path, found)


async def _restore_parts(app, title: str, path: str, found: Inspected) -> None:
    from . import platforms as tn

    usable = [p for p in found.platforms if app.platform_ready(p)]
    missing = [p for p in found.platforms if p not in usable]
    body = summary(found)
    if missing:
        body += "\n\n" + t("Not installed here, so not offered: ${names}.", names=", ".join(NAMES[p] for p in missing))
    if not usable:
        await app.push_screen_wait(MessageScreen(title, body, kind="error"))
        return
    options = [(p, t("Restore only ${name}", name=NAMES[p])) for p in usable]
    if len(usable) > 1:
        options.insert(0, ("both", t("Restore all selected platforms")))
    choice = await app.push_screen_wait(ChoiceScreen(title, body + "\n\n" + t(
        "Restoring without the recovery phrase brings the data back, and this installation keeps its own "
        "configuration (keys and passwords); a configuration encrypted in the backup is asked for or "
        "skipped by each restore."), options))
    if choice is None:
        return
    chosen = usable if choice == "both" else [choice]
    if found.kind == "tainacan-package":
        await tn.tainacan_restore(app, path)
        return
    result = await run_task(app, t("Extracting the backup safely"), "set-unpack", path)
    out = result.value if isinstance(result.value, TaskOutcome) else None
    stage = out.results.get("stage", "") if out else ""
    if not stage or not out.ok:
        await show_failure(app, title, result)
        return
    try:
        if 'dspace' in chosen:
            from . import dspace
            ds_path = out.results.get('dspace')
            if not ds_path or not await dspace.restore_path(app,ds_path):
                return  # no other platform is changed after a refused/cancelled DSpace recovery
        for pid in chosen:
            if pid == 'dspace': continue
            if pid == "koha" and out.results.get("koha"):
                from . import backup
                if await backup.restore(app, out.results["koha"]) and _has_koha_extras(found):
                    await koha_extras(app, title, stage, found)
            elif pid == "tainacan" and out.results.get("tainacan"):
                await tn.tainacan_restore(app, out.results["tainacan"])
            else:
                await app.push_screen_wait(MessageScreen(title, t(
                    "${name} is not usable in this backup: its own check failed. Nothing of it was restored.",
                    name=NAMES[pid]), kind="error"))
    finally:
        try:
            await app.bridge.task("set-cleanup", stage)
        except Exception:  # noqa: BLE001 - the staging folder is the installer's to remove later
            pass


# ----------------------------------------------------------------------
# Koha's files and secrets, after its database (installer: kei_set_koha_extras)
# ----------------------------------------------------------------------
def _has_koha_extras(found: Inspected) -> bool:
    koha = next((p for p in found.parts if p.id == "koha"), None)
    return found.koha_files or bool(koha and koha.secrets == "gpg")


ACTIONS = {
    "restore": "${label}: back to ${where} (what is there is kept first in a safety copy)",
    "apply": "Koha's encryption key: the one of the backup replaces this server's; the rest of koha-conf.xml "
             "(database password, paths, Zebra, memcached) stays as it is. The current file is kept beside it.",
    "same": "${label}: already the same here, nothing changes",
    "absent": "Koha's encryption key: not in the backup, nothing changes",
    "add": "${label}: added (this server has none)",
    "beside": "${label}: this server keeps its own; the one of the backup is saved as ${where} for you to compare",
}


def plan_lines(out: TaskOutcome) -> list[str]:
    """The plan in words. Paths and states only: never a value."""
    lines = []
    for line in out.lists.get("item", []):
        label, action, where = (line.split("\t") + ["", ""])[:3]
        if action in ACTIONS:
            lines.append("• " + t(ACTIONS[action], label=label, where=where))
    return lines


SECRETS = {
    "missing": "The secrets were not opened (no recovery phrase): only the files are in the plan.",
    "wrong": "The recovery phrase does not open the secrets (or the backup was made with another server's key): "
             "only the files are in the plan.",
    "none": "This backup has no Koha secrets: only the files are in the plan.",
}


async def koha_extras(app, title: str, stage: str, found: Inspected) -> None:
    """The plan, a Yes, then Koha's files and secrets applied."""
    from ..screens.dialogs import InputScreen
    from . import platforms as tn
    from .common import failed

    if not app.bridge.has_task("set-koha-extras"):
        return
    koha = next((p for p in found.parts if p.id == "koha"), None)
    phrase = ""
    if koha and koha.secrets == "gpg":
        phrase = await app.push_screen_wait(InputScreen(
            t("Koha's files and secrets"), t(
                "Koha's secrets in this backup (its encryption key, SIP2 and panel logins) are encrypted. Type "
                "the recovery phrase to see the plan for them, or leave it empty for the files only. Nothing "
                "changes before you say Yes to the plan."),
            t("Recovery phrase (optional)"), password=True, validate=lambda _value: ""))
        if phrase is None:
            return
    env = tn._phrase_env(phrase)
    while True:
        plan = await run_task(app, t("Koha's files and secrets"), "set-koha-extras", "plan", stage, env=env)
        if failed(plan):
            await show_failure(app, title, plan)
            return
        state = plan.value.results.get("secrets", "")
        if state != "nokey" or not phrase:
            break
        # Another server: its backup key comes from the recovery kit of the server that made the backup.
        if not await app.push_screen_wait(ConfirmScreen(title, t(
                "This server does not have the backup key the secrets were encrypted with. Import the recovery "
                "kit of the server that made the backup? (Without it, only the files come back.)"))):
            state = "missing"
            break
        kit = await app.push_screen_wait(PathPickerScreen(title, "/root", mode="file", suffixes=()))
        if kit is None:
            state = "missing"
            break
        imported = await run_task(app, t("Recovery kit"), "platform-backup-kit-import", str(kit), env=env)
        if failed(imported):
            await show_failure(app, title, imported)
            state = "missing"
            break
    lines = plan_lines(plan.value)
    if state in SECRETS or state == "nokey":
        lines.append(t(SECRETS.get(state, SECRETS["missing"])))
    if not any(line.startswith("•") for line in lines):
        await app.push_screen_wait(MessageScreen(title, "\n".join(lines) or t("Nothing to bring back."), kind="info"))
        return
    if not await app.push_screen_wait(ConfirmScreen(t("Koha's files and secrets"), t(
            "After the database, this brings back what Koha keeps outside it:") + "\n\n" + "\n".join(lines)
            + "\n\n" + t("Apply this plan?"), danger=True)):
        return
    result = await run_task(app, t("Koha's files and secrets"), "set-koha-extras", "apply", stage, "confirm",
                            env=env)
    if failed(result):
        await show_failure(app, title, result)
        return
    body = t("Koha's files and secrets were brought back as in the plan.")
    if result.value.results.get("safety"):
        body += "\n\n" + t("Safety copy of the files replaced: ${file}", file=result.value.results["safety"])
    await app.push_screen_wait(MessageScreen(title, body, kind="ok"))
