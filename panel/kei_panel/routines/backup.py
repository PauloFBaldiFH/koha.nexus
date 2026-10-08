"""Backup center and restore, as panel screens.

  manual_backup  folder picker -> backup under Pac-Man -> file, size and the
                 scp command to copy it to a PC
  test_backup    which backup (newest, or another file) -> trial import ->
                 tables, records, patrons
  restore        how to send a file + file picker (a file can be dropped on
                 it) -> a file on the Windows disk is copied in first ->
                 file check -> the questions about a suspicious file ->
                 REPLACE confirmation -> the restore (cannot be cancelled
                 halfway) -> result
  download_latest
                 the newest backup copied to the Downloads folder of this
                 PC (WSL: Windows; a Linux desktop), with size, speed and
                 time left; over SSH, the scp command instead
  cloud_backup   Google Drive with a token from another PC, or authorized on
                 this server (both untouched); or another service step by
                 step (cloud_provider): OneDrive with a sign-in link to copy
                 and the answer pasted back (screens/oauth.py), MEGA, or an
                 S3 bucket (AWS, Cloudflare R2, Wasabi, MinIO...), and rclone's
                 own wizard for the rest
Texts are the installer's own (same translations as the classic panel).
"""

from __future__ import annotations

from pathlib import Path

from .. import cloud, transfer
from ..i18n import t
from ..screens.dialogs import ChoiceScreen, ConfirmScreen, InputScreen, MessageScreen
from ..screens.files import PathPickerScreen
from ..screens.loading import LoadingScreen
from ..screens.oauth import OAuthScreen
from .common import facts, failed, last_message, run_task, show_failure, tx

DOWNLOAD_LABEL = "⬇️ Download latest backup"

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
    here = transfer.where() in ("wsl", "desktop")
    choice = await app.push_screen_wait(MessageScreen(
        t("BACKUP GENERATED AND VERIFIED SUCCESSFULLY!"), "",
        details=[(t("File:"), out.get("file")), (t("Size:"), out.get("size"))],
        command=out.get("scp"),
        command_help=f"\n{t('HOW TO SAVE TO YOUR DOWNLOADS FOLDER (WINDOWS / MAC / LINUX)')}\n{steps}",
        command_notes=after, extra=t(DOWNLOAD_LABEL) if here else ""))
    if choice == "extra":
        await download_latest(app, file=out.get("file"))


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
        # another computer, which fetches the file itself.
        user, ip = info.get("real_user", "root"), info.get("server_ip")
        await app.push_screen_wait(MessageScreen(
            title, t("This panel runs on another computer (SSH): download the backup with the command below, "
                     "on your computer."),
            kind="info", command=f"scp {user}@{ip}:{src} Downloads/",
            command_help=t("Open Terminal or PowerShell on your personal computer and paste the exact command:")))
        return
    app.notify(tx("Backup saved in your Downloads folder: ${file}", file=saved.name), timeout=8)
    await app.push_screen_wait(MessageScreen(title, "", details=[
        (t("File:"), saved.name), (t("Size:"), transfer.human_size(saved.stat().st_size)),
        (t("Folder"), str(saved.parent))]))


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


# The commands of token_instructions, each with its Copy button.
TOKEN_COMMANDS = [
    'rclone authorize "drive"',
    "winget install Rclone.Rclone",
    "wsl --shutdown\nnet stop winnat\nnet stop hns\n"
    "netsh int ipv4 set dynamic tcp start=49152 num=16384\n"
    "netsh int ipv6 set dynamic tcp start=49152 num=16384\n"
    'rclone authorize "drive"',
]


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
            ("providers", t("Other services: OneDrive, MEGA or S3 (step by step)")),
        ], note=note))
    if choice == "token":
        token = await app.push_screen_wait(InputScreen(
            t("EXPRESS GOOGLE DRIVE CONFIGURATION (VIA PERSONAL PC)"), token_instructions(),
            t("Paste the complete token JSON string below and press [ENTER]:"), validate=token_problem,
            commands=TOKEN_COMMANDS))
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
    elif choice == "providers":
        await cloud_provider(app)


async def rclone_wizard(app, title: str) -> None:
    """rclone's own text wizard, for the services the panel has no form for."""
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


# ----------------------------------------------------------------------
# OneDrive, MEGA, S3: rclone remotes without the rclone command line
# ----------------------------------------------------------------------
async def cloud_provider(app) -> None:
    title = t("Cloud Backup")
    options = [(key, t(label)) for key, label in cloud.PROVIDERS.items()]
    options.append(("wizard", t("Another service (rclone's own wizard)")))
    provider = await app.push_screen_wait(ChoiceScreen(
        title, t("Where should the backups go? The Google Drive options stay in the previous menu."), options))
    if provider is None:
        return
    if provider == "wizard":
        await rclone_wizard(app, title)
        return
    service = t(cloud.PROVIDERS[provider])
    name = await app.push_screen_wait(InputScreen(
        service, t("A short name for this connection in rclone (it also names it in the backup log)."),
        t("Connection name"), value=provider, validate=lambda v: t(cloud.name_problem(v)) if cloud.name_problem(v) else ""))
    if name is None:
        return
    values = await _provider_values(app, provider, service)
    if values is None:
        return
    try:
        path = cloud.settings_file(name, provider, values)
    except ValueError:
        await app.push_screen_wait(MessageScreen(title, t("An answer has a tab or a line break. Type it again."),
                                                 kind="error"))
        return
    try:
        result = await run_task(app, t("Testing the real cloud upload..."), "cloud-provider", str(path))
    finally:
        path.unlink(missing_ok=True)
    await _cloud_result(app, title, result)


def _need(problem_of=None):
    def check(value: str) -> str:
        if not value:
            return t("Cannot be empty.")
        problem = problem_of(value) if problem_of else ""
        return t(problem) if problem else ""
    return check


async def _provider_values(app, provider: str, service: str) -> dict[str, str] | None:
    ask = app.push_screen_wait
    if provider == "onedrive":
        auth = cloud.DemoAuthorizer("onedrive") if app.env.demo else cloud.Authorizer("onedrive")
        if not app.env.demo:
            prep = await run_task(app, t("Installing rclone"), "cloud-prepare")
            if failed(prep):
                await show_failure(app, service, prep)
                return None
        token = await ask(OAuthScreen(t("Sign in to ${service}", service=service), service, auth))
        return {"token": token} if token else None
    if provider == "mega":
        user = await ask(InputScreen(service, t("The e-mail and password of the library's MEGA account. The "
                                                "password is kept only in rclone's private file, scrambled."),
                                     t("E-mail"), validate=_need()))
        if user is None:
            return None
        password = await ask(InputScreen(service, "", t("Password"), password=True, validate=_need()))
        return None if password is None else {"user": user, "pass": password}
    # S3 and compatible
    kind = await ask(ChoiceScreen(service, t("Which service?"), [(k, t(v)) for k, v in cloud.S3_PROVIDERS.items()]))
    if kind is None:
        return None
    keys = t("An access key of the account, with permission to write in the bucket. It is kept only in rclone's "
             "private file.")
    key_id = await ask(InputScreen(service, keys, t("Access key ID"), validate=_need()))
    if key_id is None:
        return None
    secret = await ask(InputScreen(service, keys, t("Secret access key"), password=True, validate=_need()))
    if secret is None:
        return None
    values = {"provider": kind, "access_key_id": key_id, "secret_access_key": secret}
    if kind == "AWS":
        region = await ask(InputScreen(service, t("The region of the bucket, for example us-east-1 or sa-east-1."),
                                       t("Region"), value="us-east-1", validate=_need()))
        if region is None:
            return None
        values["region"] = region
    else:
        endpoint = await ask(InputScreen(service, t("The address of the service (for Cloudflare R2: "
                                                    "https://ACCOUNT_ID.r2.cloudflarestorage.com)."),
                                         t("Endpoint"), validate=_need(cloud.endpoint_problem)))
        if endpoint is None:
            return None
        values["endpoint"] = endpoint
    bucket = await ask(InputScreen(service, t("The bucket the backups go in (created if it does not exist)."),
                                   t("Bucket"), validate=_need(cloud.bucket_problem)))
    if bucket is None:
        return None
    values["bucket"] = bucket
    return values
