"""Backup center and restore, as panel screens.

  manual_backup  folder picker -> backup under Pac-Man -> file, size and the
                 scp command to copy it to a PC
  test_backup    which backup (newest, or another file) -> trial import ->
                 tables, records, patrons
  restore        how to send a file + file picker -> file check -> the
                 questions about a suspicious file -> REPLACE confirmation
                 -> the restore (cannot be cancelled halfway) -> result
  cloud_backup   Google Drive with a token from another PC, authorized on
                 this server, or any rclone remote (rclone's own wizard)
Texts are the installer's own (same translations as the classic panel).
"""

from __future__ import annotations

from pathlib import Path

from ..i18n import t
from ..screens.dialogs import ChoiceScreen, ConfirmScreen, InputScreen, MessageScreen
from ..screens.files import PathPickerScreen
from .common import facts, failed, last_message, run_task, show_failure, tx

RESTORE_STEPS = 10   # tui_run steps of function_restore_database


def _places(info) -> list[tuple[str, str]]:
    return [
        (t("Home"), info.get("real_home", "/root")),
        (t("Backups"), info.get("dir_sql", "/var/backups/koha_sql")),
        ("/media", "/media"),
        ("/mnt", "/mnt"),
    ]


# ----------------------------------------------------------------------
# Manual backup
# ----------------------------------------------------------------------
async def manual_backup(app) -> None:
    info = await facts(app)
    srv_ip = info.get("server_ip")
    folder = await app.push_screen_wait(PathPickerScreen(
        t("Backup Destination"), info.get("real_home", "/root"), mode="dir", shortcuts=_places(info),
        help_text=tx("Choose where to save the file.\n\n  USB drive: usually under /media or /mnt\n  "
                     "To download later: scp root@${srv_ip}:PATH Downloads/", srv_ip=srv_ip)))
    if folder is None:
        return
    title = t("💾  Generate manual backup and download to PC")
    result = await run_task(app, tx("Generating the backup..."), "backup-manual", str(folder))
    if failed(result):
        await show_failure(app, title, result)
        return
    out = result.value
    user = out.get("user", "root")
    steps = t("Open Terminal or PowerShell on your personal computer and paste the exact command:")
    after = "\n".join([
        t("1. The file will be saved directly into your Downloads folder."),
        t("2. Make sure to include 'Downloads/' at the end of the command."),
        tx("3. You will be asked for the password of user '${REAL_USER:-root}'.", REAL_USER=user),
    ])
    await app.push_screen_wait(MessageScreen(
        t("BACKUP GENERATED AND VERIFIED SUCCESSFULLY!"), "",
        details=[(t("File:"), out.get("file")), (t("Size:"), out.get("size"))],
        command=out.get("scp"),
        command_help=f"\n{t('HOW TO SAVE TO YOUR DOWNLOADS FOLDER (WINDOWS / MAC / LINUX)')}\n{steps}",
        command_notes=after))


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
    if not file:
        picked = await app.push_screen_wait(PathPickerScreen(
            title, info.get("real_home", "/root"), mode="file", shortcuts=_places(info),
            help_text=transfer_help(info)))
        if picked is None:
            return
        file = str(picked)

    check = await run_task(app, tx("Checking the backup file..."), "restore-check", file)
    if failed(check):
        await show_failure(app, title, check)
        return
    out = check.value
    if out.get("has_sql") != "yes":
        question = ("No SQL statements found at the start of the file.\nIt may not be a Koha backup.\n\n"
                    "Continue anyway?") if file.endswith(".gz") else \
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
# Cloud backup (rclone)
# ----------------------------------------------------------------------
def token_problem(token: str) -> str:
    """The checks of the classic routine, with its messages."""
    if not token:
        return tx("[ERROR] Token cannot be empty. Try again or press Ctrl+C to cancel.").split(" Try")[0]
    if not (token.startswith("{") and token.endswith("}")):
        return t("[ERROR] Invalid format! Token must start with '{' and end with '}'. Try again:")
    if not all(k in token for k in ('"access_token"', '"refresh_token"', '"expiry"')):
        return t("[ERROR] Provided JSON is corrupt or was truncated when copying. Try again:")
    return ""


def token_instructions() -> str:
    return "\n".join([
        t("Because this server has no direct web browser, you can authorize"),
        t("the connection from your personal computer (Windows/Mac/Linux)."), "",
        t("STEP 1: On your personal PC, open PowerShell as an admin (Windows) or Terminal (Mac/Linux)."),
        t("If on Windows and 'rclone' is not recognized, install with: winget install Rclone.Rclone"), "",
        '  rclone authorize "drive"', "",
        t("If the above command gives a socket/port error on Windows, run as Administrator:"), "",
        "  wsl --shutdown", "  net stop winnat", "  net stop hns",
        "  netsh int ipv4 set dynamic tcp start=49152 num=16384",
        "  netsh int ipv6 set dynamic tcp start=49152 num=16384",
        '  rclone authorize "drive"', "",
        t("STEP 2: Your browser will open. Log in with the library Google account and authorize."),
        t("STEP 3: Your PC will print a long token string starting with '{\"' and ending with '}'."),
    ])


async def _cloud_result(app, title: str, result) -> None:
    if failed(result):
        await show_failure(app, title, result)
        return
    kind, head, body = last_message(result.value, t("Cloud configured"))
    await app.push_screen_wait(MessageScreen(head or t("Cloud configured"), body, kind=kind))


async def cloud_backup(app) -> None:
    info = await facts(app)
    title = t("Cloud Backup")
    current = info.get("rclone_remote")
    note = f"{t('Remote')}: {current}" if current else ""
    choice = await app.push_screen_wait(ChoiceScreen(
        title, t("How do you want to configure auto cloud backups?"), [
            ("token", t("Express: Generate token on another PC (SSH / Headless)")),
            ("here", t("Express: Authenticate directly on this server")),
            ("wizard", t("Manual: Standard Rclone Wizard (Other services)")),
        ], note=note))
    if choice == "token":
        token = await app.push_screen_wait(InputScreen(
            t("EXPRESS GOOGLE DRIVE CONFIGURATION (VIA PERSONAL PC)"), token_instructions(),
            t("Paste the complete token JSON string below and press [ENTER]:"), validate=token_problem))
        if token is None:
            return
        result = await run_task(app, t("Registering 'gdrive' remote in Rclone..."), "cloud-token",
                                env={"KEI_RCLONE_TOKEN": token})
        await _cloud_result(app, title, result)
    elif choice == "here":
        def on_result(reporter, key: str, value: str) -> None:
            if key == "auth_url":
                state["text"] = f"{t('Open this link in a browser:')}\n\n{value}"
            elif key == "auth_tunnel":
                state["text"] += "\n\n" + t("This server has no browser. On your PC, first open an SSH tunnel:") \
                    + f"\n  {value}\n" + t("then open the link in the browser of that PC.")
            elif key == "auth_opened":
                state["text"] += "\n\n" + t("The link was opened in the browser. Authorize there, then come back here.")
            else:
                return
            reporter.notice(state["text"] + "\n\n" + t("Waiting for the authorization..."))

        state = {"text": ""}
        result = await run_task(app, t("DIRECT SERVER AUTHENTICATION (LOCAL / WITH BROWSER OR TUNNEL)"),
                                "cloud-authorize", on_result=on_result)
        await _cloud_result(app, title, result)
    elif choice == "wizard":
        prep = await run_task(app, t("Installing rclone"), "cloud-prepare")
        if failed(prep):
            await show_failure(app, title, prep)
            return
        app.bridge.run_command_interactive(app, ["rclone", "config"])
        remotes = (await app.bridge.task("cloud-remotes")).lists.get("remote", [])
        if not remotes:
            await app.push_screen_wait(MessageScreen(title, tx(
                "There is no rclone remote called '$name'.\n\nExisting remotes:\n$remotes",
                name="", remotes="-"), kind="error"))
            return
        name = await app.push_screen_wait(ChoiceScreen(
            t("Remote Name"), t("Enter the EXACT NAME configured in Rclone:"), [(r, r) for r in remotes]))
        if name is None:
            return
        result = await run_task(app, t("Testing the real cloud upload..."), "cloud-remote", name)
        await _cloud_result(app, title, result)
