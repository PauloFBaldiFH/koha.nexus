"""The joint package (Koha + Tainacan) and the assisted restore, in the
Backup center (Paulo, 2026-11-06). The installer does the work
(kei_set_backup, kei_set_inspect, kei_set_unpack, kei_set_cleanup); the
restores themselves are the routines that already existed: Koha's
"Restore database" (restore-check, its safety backup) and "Restore
Tainacan" (the test in an isolated copy, its safety backup, the recovery
phrase), so their confirmations are kept.

A file is recognised by its content, never its name. Nothing a manifest
says is run: it is only read and shown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..bridge import TaskOutcome
from ..i18n import t
from ..screens.dialogs import ChoiceScreen, ConfirmScreen, MessageScreen
from ..screens.files import PathPickerScreen
from .common import facts, run_task, show_failure

NAMES = {"koha": "Koha", "tainacan": "Tainacan"}


@dataclass
class Part:
    """One platform of a set: its capture, as the set's manifest says."""
    id: str
    ok: bool
    started: str = ""
    finished: str = ""
    secrets: str = ""
    error: str = ""


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


def parse_inspect(out: TaskOutcome) -> Inspected:
    r = out.results
    info = Inspected(kind=r.get("kind", "unknown"), why=r.get("why", ""), created=r.get("created", ""),
                     host=r.get("host", ""), version=r.get("panel_version", ""),
                     complete=r.get("complete", "yes") != "no", integrity=r.get("integrity", ""),
                     platforms=[p for p in r.get("platforms", "").split() if p in NAMES])
    for line in out.lists.get("part", []):
        cols = (line.split("\t") + [""] * 6)[:6]
        if cols[0] in NAMES:
            info.parts.append(Part(cols[0], cols[1] == "ok", cols[2], cols[3], cols[4], cols[5]))
    for line in out.lists.get("conflict", []):
        pid, _sep, text = line.partition("\t")
        if pid in NAMES:
            info.conflicts[pid] = text
    return info


def parse_backup(out: TaskOutcome) -> list[Part]:
    """The platform lines of set-backup: ID, ok|failed, start, end, path or why."""
    parts = []
    for line in out.lists.get("platform", []):
        cols = (line.split("\t") + [""] * 5)[:5]
        if cols[0] in NAMES:
            ok = cols[1] == "ok"
            parts.append(Part(cols[0], ok, cols[2], cols[3], error="" if ok else cols[4]))
    return parts


def secrets_text(part: Part) -> str:
    """What of a part is encrypted: never "encrypted" for the whole."""
    if part.id == "koha":
        return t("Koha configuration encrypted with this server's key (never applied by a restore)") \
            if part.secrets == "gpg" else t("Koha configuration not included")
    return t("configuration encrypted with the backup key") if part.secrets == "gpg" \
        else t("configuration not encrypted (readable by root only)")


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
    for pid, text in info.conflicts.items():
        lines.append(f"{NAMES[pid]}: {text}")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Joint backup
# ----------------------------------------------------------------------
async def set_backup(app) -> None:
    title = t("📦  Joint backup (Koha + Tainacan)")
    info = await facts(app)
    home = info.get("real_home") or "/root"
    start = Path(home) / "backups"
    folder = await app.push_screen_wait(PathPickerScreen(
        title, start if start.is_dir() else home, mode="dir",
        help_text=t("Choose the folder of this server where the joint package is saved.")))
    if folder is None:
        return
    if not await app.push_screen_wait(ConfirmScreen(title, t(
            "One file with the data of Koha and of Tainacan, and a manifest with the checksums. Each platform "
            "is captured in turn with its own consistent copy (Tainacan stops writing for a moment), and the "
            "time of each capture is recorded: the two are not taken at the same instant. Make it now?"))):
        return
    result = await run_task(app, title, "set-backup", str(folder))
    out = result.value if isinstance(result.value, TaskOutcome) else None
    parts = parse_backup(out) if out else []
    file = out.results.get("file", "") if out else ""
    if result.cancelled or not file:
        await show_failure(app, title, result)
        return
    lines = []
    for part in parts:
        mark = "✅" if part.ok else "⚠"
        what = f"{part.started} → {part.finished}" if part.ok else part.error
        lines.append(f"{mark} {NAMES[part.id]}: {what}")
    body = "\n".join(lines) + "\n\n" + t("File: ${file}", file=file)
    if out.results.get("complete") == "yes":
        await app.push_screen_wait(MessageScreen(title, t("✅ Joint backup done.") + "\n\n" + body, kind="ok"))
    else:
        await app.push_screen_wait(MessageScreen(title, t(
            "⚠ The joint backup is NOT complete: the platform marked ⚠ below is not in it. The part that worked is "
            "in the file (named -partial). Fix the cause shown next to it and make the joint backup again; each "
            "platform can also be backed up on its own in the Backup center.") + "\n\n" + body, kind="error"))


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
        options.insert(0, ("both", t("Restore Koha and Tainacan")))
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
        for pid in chosen:
            if pid == "koha" and out.results.get("koha"):
                from . import backup
                await backup.restore(app, out.results["koha"])
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
