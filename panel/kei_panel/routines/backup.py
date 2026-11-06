"""Backup center and restore, as panel screens.

  manual_backup  the save screen (screens/save_backup): folder of this server
                 (~/backups) -> backup with progress -> copy to Windows
                 Downloads or a folder in Windows (WSL2), or the scp command
  marc_backup    the weekly MARC21 export (bibliographic + authority
                 records, koha_marc_<date>.tar.gz) run now -> file, size,
                 the scp command and, on WSL or a Linux desktop, a button
                 that copies the .tar.gz to the Downloads folder
  test_backup    which backup (newest, or another file) -> trial import ->
                 tables, records, patrons
  restore        over SSH: from the browser (webtransfer) or a file here;
                 how to send a file + file picker (a file can be dropped on
                 it) -> a file on the Windows disk is copied in first ->
                 file check -> the questions about a suspicious file ->
                 REPLACE confirmation -> the restore (cannot be cancelled
                 halfway) -> result
  download_latest
                 the newest backup copied to the Downloads folder of this
                 PC (WSL: Windows; a Linux desktop), with size, speed and
                 time left, then shown selected in Explorer (WSL) or its
                 folder opened (desktop); over SSH, a page the browser of
                 the person's computer saves it from (webtransfer)
  cloud_backup   the automatic cloud backup screen (screens/cloud_backup):
                 connections to any rclone service drawn from rclone's own
                 catalog (screens/cloud_remote, sign-in links in
                 screens/oauth), destination folder, schedule, retention in
                 the cloud, second copy, speed limit, the backups in the
                 cloud (download, restore, delete) and the history
Texts are the installer's own (same translations as the classic panel).
"""

from __future__ import annotations

from pathlib import Path

from .. import transfer
from ..i18n import t
from ..opener import reveal_file
from ..screens.dialogs import ChoiceScreen, ConfirmScreen, MessageScreen
from ..screens.files import PathPickerScreen
from ..screens.loading import LoadingScreen
from ..screens.save_backup import SaveBackupScreen
from ..screens.web_transfer import WebTransferScreen, browser_server
from .common import facts, failed, run_task, show_failure, tx

DOWNLOAD_LABEL = "📥 Download latest backup"
DOWNLOAD_FILE = "📥 Download to computer"

RESTORE_STEPS = 10   # tui_run steps of function_restore_database


def _places(info) -> list[tuple[str, str]]:
    return [
        (t("Home"), info.get("real_home", "/root")),
        (t("Backups"), info.get("dir_sql", "/var/backups/koha_sql")),
        ("/media", "/media"),
        ("/mnt", "/mnt"),
    ]


def _reveal(app, path: str) -> None:
    """The file shown selected in Windows Explorer (or its folder on a
    desktop), so nobody has to type a Linux path to find it."""
    if not app.env.demo and reveal_file(path):
        app.notify(tx("Shown in the file manager: ${file}", file=Path(path).name), timeout=6)


# ----------------------------------------------------------------------
# Manual backup
# ----------------------------------------------------------------------
async def manual_backup(app) -> None:
    """Save a backup into a folder of this server (~/backups by default), then
    the ways to get it to the person: Windows Downloads or a folder in Windows
    (WSL2 only), or the scp command for another computer. See screens/save_backup."""
    info = await facts(app)
    await app.push_screen_wait(SaveBackupScreen(info))


# ----------------------------------------------------------------------
# MARC21 export now (the weekly /root/backup_marc.sh, run at once)
# ----------------------------------------------------------------------
async def marc_backup(app) -> None:
    """Export the MARC21 records into a folder of this server (~/backups by
    default), then the ways to get the package to the person: the same
    screen as the manual backup (screens/marc_export, screens/save_backup)."""
    from ..screens.marc_export import MarcExportScreen
    info = await facts(app)
    marc = await app.bridge.task("marc-info")
    await app.push_screen_wait(MarcExportScreen(info, marc))


# ----------------------------------------------------------------------
# Test the latest backup
# ----------------------------------------------------------------------
async def test_backup(app) -> None:
    info = await facts(app)
    title = t("Test Backup")
    newest = info.get("newest")
    intro = t("A backup is only worth it if it restores. This test imports the newest file into a "
              "temporary database and checks it. Production data is NOT touched.")
    options = [("other", t("Choose another file"))]
    if newest:
        body = f"{intro}\n\n{t('File')}: {Path(newest).name}\n{t('Date')}: {info.get('newest_date')}"
        options.insert(0, ("newest", t("Run the test now?")))
    else:
        body = tx("No automatic backup found in ${DIR_SQL}.", DIR_SQL=info.get("dir_sql"))
    choice = await app.push_screen_wait(ChoiceScreen(title, body, options))
    if choice is None:
        return
    target = newest
    if choice == "other":
        picked = await app.push_screen_wait(PathPickerScreen(
            title, info.get("dir_sql") or info.get("real_home", "/root"), mode="file", shortcuts=_places(info)))
        if picked is None:
            return
        target = str(picked)
    result = await run_task(app, tx("Importing into a temporary database..."), "backup-test", target)
    if failed(result):
        await show_failure(app, title, result)
        return
    out = result.value
    await app.push_screen_wait(MessageScreen(
        t("BACKUP IS INTACT AND RESTORABLE."), "",
        details=[(t("File"), Path(out.get("file", target)).name), (t("Tables"), out.get("tables")),
                 (t("Bibliographic records"), out.get("biblios")), (t("Patrons"), out.get("patrons"))]))


# ----------------------------------------------------------------------
# Restore
# ----------------------------------------------------------------------
def send_command(info, local_path: str) -> str:
    """The command, run on the person's computer, that sends a file here."""
    user, ip, home = info.get("real_user", "root"), info.get("server_ip"), info.get("real_home", "/root")
    return f'scp "{local_path}" {user}@{ip}:{home}/'


def transfer_help(info) -> str:
    user, ip, home = info.get("real_user", "root"), info.get("server_ip"), info.get("real_home", "/root")
    return "\n".join([
        t("HOW TO SEND THE BACKUP TO THE SERVER"), "",
        t("OPTION 1 — Windows (Drag and Drop):"),
        t("1. In Notepad, paste the code below and save on Desktop as 'Send_Backup.bat':"), "",
        "@echo off", "chcp 65001 >nul", f'scp "%~1" {user}@{ip}:{home}/', "pause", "",
        t("2. Then, just DRAG the .sql file onto that icon."), "",
        t("OPTION 2 — Linux, macOS or Direct Terminal:"),
        f'    scp "backup_file.sql" {user}@{ip}:{home}/', "",
        t("OPTION 3 — USB drive: plug into server and check /media or /mnt"),
    ])


async def restore(app, file: str | None = None) -> None:
    info = await facts(app)
    title = t("📥  Restore database")
    if not file and transfer.where() in ("ssh", "server"):
        # The person's computer is elsewhere: the file can come through
        # their browser (webtransfer), or be one already on this server.
        choice = await app.push_screen_wait(ChoiceScreen(title, t(
            "This panel runs on another computer (SSH). Where is the backup?"), [
            ("browser", t("🌐 On my computer: send it through the browser")),
            ("server", t("🗄  Already on this server: choose the file"))]))
        if choice is None:
            return
        if choice == "browser":
            received = await receive_from_browser(app, info, title)
            if received is None:
                return
            file = str(received)
    if not file:
        picked = await app.push_screen_wait(PathPickerScreen(
            title, info.get("real_home", "/root"), mode="file", shortcuts=_places(info),
            help_text=transfer_help(info), commands=[send_command(info, "backup_file.sql")],
            send_command=lambda path: send_command(info, path)))
        if picked is None:
            return
        file = str(picked)

    staged = None
    if transfer.on_windows_disk(file):
        # A file of the Windows disk (dropped on the panel under WSL) is
        # copied in first: the restore then reads a local, stable copy.
        staged = await _copy_in(app, title, Path(file), Path(info.get("dir_sql", "/var/backups/koha_sql")))
        if staged is None:
            return
        file = str(staged)
    try:
        await _restore_file(app, title, file)
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


async def receive_from_browser(app, info, title: str) -> Path | None:
    """A backup sent from the person's computer through the browser, checked
    (size and SHA-256); None when the screen was closed first."""
    return await app.push_screen_wait(WebTransferScreen(
        title, browser_server(info, "upload"), user=info.get("real_user", "root")))


async def _copy_in(app, title: str, src: Path, backups: Path) -> Path | None:
    folder = backups / "incoming"

    def job(reporter):
        folder.mkdir(parents=True, exist_ok=True)
        return transfer.copy_file(src, transfer.free_target(folder, src.name), reporter)

    result = await app.push_screen_wait(LoadingScreen(t("Copying the backup file"), job))
    if result.ok:
        return result.value
    await _copy_failed(app, title, result)
    return None


async def _copy_failed(app, title: str, result) -> None:
    if result.cancelled:
        app.notify(f"{title}: {t('Cancelled')}", severity="warning")
        return
    await app.push_screen_wait(MessageScreen(title, result.error or t("Unknown error."), kind="error"))


async def _restore_file(app, title: str, file: str) -> None:
    check = await run_task(app, tx("Checking the backup file..."), "restore-check", file)
    if failed(check):
        await show_failure(app, title, check)
        return
    out = check.value
    if out.get("has_sql") != "yes":
        question = ("No SQL statements found at the start of the file.\nIt may not be a Koha backup.\n\n"
                    "Continue anyway?") if file.endswith((".gz", ".bz2", ".xz", ".zst")) else \
            "No SQL statements found at the start of the file.\n\nContinue anyway?"
        if not await app.push_screen_wait(ConfirmScreen(t("Suspicious file"), tx(question))):
            return
    if out.get("complete") != "yes":
        if not await app.push_screen_wait(ConfirmScreen(t("Suspicious file"), tx(
                "The file does not end with the mysqldump completion line (-- Dump completed): it may be "
                "truncated.\n\nContinue anyway? It will still be tested in a temporary database first."))):
            return
    question = tx("File:\n$file\n\nWARNING: the current catalog will be REPLACED.\n\nContinue?", file=file)
    question += f"\n\n{t('Size:')} {out.get('size_mb')} MB · {t('Free')}: {out.get('free_mb')} MB"
    if not await app.push_screen_wait(ConfirmScreen(t("Confirm Restore"), question, danger=True)):
        return

    result = await run_task(app, t("Restoring the catalog"), "restore", file,
                            cancellable=False, total_steps=RESTORE_STEPS)
    # The database changed (even a failed restore may have brought the safety
    # backup back): screens that show what is in Koha, such as OPAC and Staff
    # Appearance, read it again when shown.
    app.restores = getattr(app, "restores", 0) + 1
    if failed(result):
        await show_failure(app, title, result)
        return
    done = result.value
    details = [(t("Search engine"), done.get("engine")), (t("Tables"), done.get("tables"))]
    if done.get("safety_backup"):
        details.append((t("Safety backup:"), done.get("safety_backup")))
    await app.push_screen_wait(MessageScreen(
        tx("Catalog restored and indexed successfully!\n\nSearch engine: ${engine}\nTables: ${tables}",
           engine=done.get("engine"), tables=done.get("tables")).splitlines()[0], "", details=details))


# ----------------------------------------------------------------------
# Download the latest backup to this PC
# ----------------------------------------------------------------------
async def download_latest(app, file: str | None = None) -> None:
    title = t(DOWNLOAD_LABEL)
    info = await facts(app)
    src = Path(file or info.get("newest") or "")
    if not str(src) or str(src) == "." or not src.is_file():
        await app.push_screen_wait(MessageScreen(title, tx("No backup found in ${dir}.", dir=info.get("dir_sql")),
                                                 kind="error"))
        return
    await download_file(app, src, title, info)


async def download_file(app, src: Path, title: str, info: dict | None = None) -> None:
    """src (a backup or the MARC21 package) copied to the Downloads folder."""
    if not src.is_file():
        await app.push_screen_wait(MessageScreen(title, f"{t('File not found.')}\n{src}", kind="error"))
        return
    info = info if info is not None else await facts(app)
    place = transfer.where()

    def job(reporter):
        reporter.status(t("Looking for the Downloads folder..."))
        folder = transfer.downloads_folder(place)
        if folder is None:
            return None
        return transfer.copy_file(src, transfer.free_target(folder, src.name), reporter,
                                  owner=transfer.desktop_owner(place))

    result = await app.push_screen_wait(LoadingScreen(t("Downloading the latest backup"), job))
    if not result.ok:
        await _copy_failed(app, title, result)
        return
    saved = result.value
    if saved is None:
        # SSH or a server without a desktop: the Downloads folder is on
        # another computer, which fetches the file through its browser
        # (webtransfer). The scp command is left for a WSL or a desktop
        # whose Downloads folder was not found.
        user, ip = info.get("real_user", "root"), info.get("server_ip")
        if place in ("ssh", "server"):
            await app.push_screen_wait(WebTransferScreen(title, browser_server(info, "download", src), user=user))
            return
        await app.push_screen_wait(MessageScreen(
            title, t("This panel runs on another computer (SSH): download the backup with the command below, "
                     "on your computer."),
            kind="info", command=f"scp {user}@{ip}:{src} Downloads/",
            command_help=t("Open Terminal or PowerShell on your personal computer and paste the exact command:")))
        return
    app.notify(tx("Backup saved in your Downloads folder: ${file}", file=saved.name), timeout=8)
    _reveal(app, str(saved))
    await app.push_screen_wait(MessageScreen(title, "", details=[
        (t("File:"), saved.name), (t("Size:"), transfer.human_size(saved.stat().st_size)),
        (t("Folder"), str(saved.parent))]))


# ----------------------------------------------------------------------
# Automatic cloud backup (rclone): one screen for all of it
# ----------------------------------------------------------------------
async def cloud_backup(app) -> None:
    """Connections to any rclone service, the backup destination and its
    folder, schedule, retention, second copy, speed limit, the files in the
    cloud and the history: screens/cloud_backup. A backup fetched there to
    be restored comes back here and goes to Restore database."""
    from ..screens.cloud_backup import CloudBackupScreen, restore_path
    info = await facts(app)
    file = restore_path(await app.push_screen_wait(CloudBackupScreen(info)))
    if file:
        await restore(app, file)


async def cloud_connections(app) -> None:
    """The Backup center's shared "Cloud connections": the rclone
    connections of this server, for any platform (Koha not needed). Only
    the connections tab: Koha's cloud backups stay in its own card, and the
    Tainacan backup copy is chosen in its card. A connection still used by
    the Tainacan copy is marked and cannot be removed here."""
    from ..screens.cloud_backup import CloudBackupScreen
    info = await facts(app)
    uses: dict[str, list[str]] = {}
    bridge = app.bridge
    try:
        if bridge.has_task("platform-backup-status"):
            out = await bridge.task("platform-backup-status", "tainacan")
            results = out.results if isinstance(out.results, dict) else {}
            for key, label in (("tainacan.copy", t("Tainacan copy")), ("tainacan.repo", t("Tainacan repository"))):
                name, sep, _path = (results.get(key) or "").removeprefix("rclone:").partition(":")
                if sep and name and "/" not in name:
                    uses.setdefault(name, []).append(label)
    except Exception:  # noqa: BLE001 - the connections are shown anyway
        pass
    await app.push_screen_wait(CloudBackupScreen(info, connections_only=True, uses=uses,
                                                 koha=app.platform_ready("koha")))
