"""SaveBackupScreen: a manual backup saved on this server, then the ways to
get it to the person (the Backup screen chose the compression already).

  ┌ Save database backup ────────────────────────────────────────────┐
  │ Save the backup in this folder of the server:                    │
  │ [/home/ana/backups_________________________________________]     │
  │ ▓▓▓▓▓▓░░░░ Saving the backup...                (while it runs)   │
  │                                           [Save backup] [Cancel] │
  ├──────────────── after the save ───────────────────────────────────┤
  │ File: koha_manual_...sql.gz   Size: 41 MB                        │
  │ scp ana@192.0.2.10:"/home/ana/backups/..." .      [📋 Copy command]│
  │ [📥 Save to Windows Downloads] [📁 Choose folder in Windows]     │
  │                                                 [Finish and exit] │
  └──────────────────────────────────────────────────────────────────┘

The save is the backup-manual routine, run by the bridge in a task of the
app's loop, so the screen keeps answering while it runs. The copies to the
Windows side are thread workers (copy_file, powershell.exe), which report
to the screen through call_from_thread. The Windows buttons exist only
under WSL2 (save_backup.is_wsl); elsewhere they are not shown at all.
Over SSH "Download in the browser" offers the file on a page of this server
(screens/web_transfer), for the browser of the person's computer.
"""

from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ProgressBar, Static

from .. import save_backup, transfer
from ..i18n import t
from ..opener import reveal_file
from ..widgets.copy import CopyButton
from .dialogs import FitsScreen


class _ThreadReporter:
    """transfer.copy_file's reporter for a copy run in a thread: progress
    and text reach the screen on the app's loop."""

    cancelled = False

    def __init__(self, screen: "SaveBackupScreen"):
        self._screen = screen

    def progress(self, done: float, total: float) -> None:
        self._screen.app.call_from_thread(self._screen.show_bar, done, total)

    def status(self, text: str) -> None:
        self._screen.app.call_from_thread(self._screen.set_status, text)


class _LoopReporter:
    """The reporter of bridge.task (log, status, notice, progress...), for the
    backup routine running on the app's loop."""

    cancelled = False

    def __init__(self, screen: "SaveBackupScreen"):
        self._screen = screen

    def log(self, line: str) -> None:
        self._screen.set_status(line)

    def status(self, text: str) -> None:
        self._screen.set_status(text)

    def notice(self, text: str) -> None:
        self._screen.set_status(text)

    def cancellable(self, on: bool) -> None:
        pass

    def progress(self, current: float, total: float) -> None:
        self._screen.show_bar(current, total)


class SaveBackupScreen(FitsScreen, ModalScreen[None]):
    BINDINGS = [Binding("escape", "close", t("Cancel"))]

    def __init__(self, info: dict):
        super().__init__()
        self._home = info.get("real_home") or "/root"
        self._default = save_backup.default_folder(self._home)
        self._user = info.get("real_user") or "root"
        self._host = save_backup.scp_host(info.get("server_ip"))
        self._wsl = save_backup.is_wsl()
        # Over SSH (or a server with no desktop) the person's computer is
        # elsewhere: its browser fetches the file (screens/web_transfer).
        self._browser = not self._wsl and transfer.where() in ("ssh", "server")
        self._info = info
        self._file: Path | None = None
        self._scp = ""
        self._busy = False      # saving, or copying to Windows: nothing closes the screen
        self._copying = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog -wide -ok"):
            yield Label(t("Save database backup"), classes="dialog-title", markup=False)
            with VerticalScroll(classes="dialog-scroll"):
                with Vertical(id="sb-form"):
                    yield Label(t("Save the backup in this folder of the server:"), classes="dialog-prompt")
                    yield Input(value=str(self._default), placeholder=str(self._default), id="sb-folder")
                    yield Label("", id="sb-problem", classes="dialog-error", markup=False)
                    yield Static(t("The compression is the one chosen on the Backup screen."),
                                 classes="dialog-note", markup=False)
                with Vertical(id="sb-progress"):
                    yield Label("", id="sb-status", markup=False)
                    yield ProgressBar(total=None, show_eta=False, id="sb-bar")
                with Vertical(id="sb-done"):
                    yield Label("", id="sb-result", markup=False)
                    yield Static(t("To copy it to your computer, open Terminal or PowerShell there and paste "
                                   "this command:"), classes="dialog-body", markup=False)
                    yield Static("", id="sb-scp", classes="dialog-command", markup=False)
                    yield Static(t("You will be asked for the password of user '${user}'.", user=self._user),
                                 classes="dialog-note", markup=False)
                    with Horizontal(classes="dialog-buttons"):
                        yield CopyButton(command=True, id="copy-scp")
            with Horizontal(id="sb-buttons-save", classes="dialog-buttons"):
                yield Button(t("Save backup"), id="save", variant="primary")
                yield Button(t("Cancel"), id="cancel")
            with Horizontal(id="sb-buttons-done", classes="dialog-buttons"):
                if self._wsl:
                    yield Button(t("📥 Save to Windows Downloads"), id="win-downloads", variant="success")
                    yield Button(t("📁 Choose folder in Windows"), id="win-pick")
                if self._browser:
                    yield Button(t("🌐 Download in the browser"), id="web-download", variant="success")
                yield Button(t("Finish and exit"), id="done", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#sb-progress").display = False
        self.query_one("#sb-done").display = False
        self.query_one("#sb-buttons-done").display = False
        self.query_one("#sb-folder", Input).focus()

    # --- step 1: the save -------------------------------------------------
    @on(Button.Pressed, "#save")
    @on(Input.Submitted, "#sb-folder")
    def _start(self) -> None:
        if self._busy:
            return
        folder, problem = save_backup.folder_problem(self.query_one("#sb-folder", Input).value, self._default)
        self.query_one("#sb-problem", Label).update(t(problem) if problem else "")
        if problem:
            return
        self._busy = True
        self.query_one("#sb-form").display = False
        self.query_one("#sb-progress").display = True
        self.query_one("#sb-buttons-save").display = False
        self.set_status(t("Saving the backup..."))
        self.show_bar(0, 0)
        self._save(folder)

    @work(exclusive=True, group="save-backup", exit_on_error=False)
    async def _save(self, folder: Path) -> None:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            out = await self.app.bridge.task("backup-manual", str(folder), reporter=_LoopReporter(self))
        except Exception as e:  # noqa: BLE001 - shown, the screen stays usable
            self._save_failed(f"{type(e).__name__}: {e}")
            return
        if not out.ok:
            msg = out.last("error")
            self._save_failed(msg[2] if msg else f"exit {out.rc}")
            return
        self._busy = False
        self._file = Path(out.get("file") or "")
        self._user = out.get("user") or self._user
        self._scp = save_backup.scp_command(self._user, self._host, str(self._file))
        self._show_done(out.get("size") or "")

    def _save_failed(self, text: str) -> None:
        self._busy = False
        self.query_one("#sb-progress").display = False
        self.query_one("#sb-form").display = True
        self.query_one("#sb-buttons-save").display = True
        self.query_one("#sb-problem", Label).update(text)
        self.query_one("#sb-folder", Input).focus()

    def _show_done(self, size: str) -> None:
        self.query_one("#sb-progress").display = False
        self.query_one("#sb-buttons-save").display = False
        self.query_one("#sb-buttons-done").display = True
        self.query_one("#sb-done").display = True
        self.query_one("#sb-result", Label).update(f"{t('File:')} {self._file}\n{t('Size:')} {size}")
        self.query_one("#sb-scp", Static).update(self._scp)
        self.query_one("#done", Button).focus()
        if self._file and transfer.on_windows_disk(self._file) and not self.app.env.demo:
            self._reveal()

    @work(thread=True, exclusive=False, group="reveal", exit_on_error=False)
    def _reveal(self) -> None:
        # The file on the Windows disk: shown selected in Explorer.
        reveal_file(str(self._file))

    def set_status(self, text: str) -> None:
        self.query_one("#sb-status", Label).update(text)

    def show_bar(self, done: float, total: float) -> None:
        self.query_one("#sb-bar", ProgressBar).update(total=total or None, progress=done)

    # --- step 2: the copies -----------------------------------------------
    @on(Button.Pressed, "#win-downloads")
    def _to_downloads(self) -> None:
        self._copy_to_windows(pick=False)

    @on(Button.Pressed, "#win-pick")
    def _to_picked(self) -> None:
        self._copy_to_windows(pick=True)

    def _copy_to_windows(self, pick: bool) -> None:
        if self._copying or self._file is None:
            return
        self._copying = True
        self._busy = True
        self.query_one("#sb-done").display = False
        self.query_one("#sb-progress").display = True
        self.query_one("#sb-buttons-done").display = False
        self.set_status(t("Choose the folder in the Windows window...") if pick
                        else t("Copying to Windows Downloads..."))
        self.show_bar(0, 0)
        self._copy_thread(pick)

    @work(thread=True, exclusive=True, group="copy-windows", exit_on_error=False)
    def _copy_thread(self, pick: bool) -> None:
        try:
            if pick:
                folder = save_backup.picked_folder(save_backup.windows_folder_dialog())
                if folder is None:
                    self.app.call_from_thread(self._copy_finished, t("No folder was chosen."), "warning")
                    return
            else:
                folder = transfer.downloads_folder("wsl")
                if folder is None:
                    self.app.call_from_thread(self._copy_finished,
                                              t("The Windows Downloads folder was not found."), "error")
                    return
            saved = transfer.copy_file(self._file, transfer.free_target(folder, self._file.name),
                                       _ThreadReporter(self))
            self.app.call_from_thread(self._copy_finished,
                                      t("Saved in ${folder}: ${file}", folder=str(saved.parent), file=saved.name),
                                      "information")
        except Exception as e:  # noqa: BLE001 - shown, the buttons come back
            self.app.call_from_thread(self._copy_finished, f"{type(e).__name__}: {e}", "error")

    def _copy_finished(self, text: str, severity: str) -> None:
        self._copying = False
        self._busy = False
        self.query_one("#sb-progress").display = False
        self.query_one("#sb-done").display = True
        self.query_one("#sb-buttons-done").display = True
        self.app.notify(text, severity=severity, timeout=8)

    # --- the end ----------------------------------------------------------
    @on(Button.Pressed, "#web-download")
    def _web_download(self) -> None:
        from .web_transfer import WebTransferScreen, browser_server
        if self._file is None or not self._file.is_file():
            return
        self.app.push_screen(WebTransferScreen(t("Save database backup"), browser_server(
            self._info, "download", self._file), user=self._user))

    @on(Button.Pressed, "#copy-scp")
    def _copy_scp(self) -> None:
        self.app.copy_to_clipboard(self._scp)

    @on(Button.Pressed, "#done")
    @on(Button.Pressed, "#cancel")
    def action_close(self) -> None:
        if self._busy:
            self.app.notify(t("Wait until the backup is saved."), severity="warning")
            return
        # Done or Cancel: the file stays on the server either way; nothing is deleted here.
        self.dismiss(None)
