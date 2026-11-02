"""SaveBackupScreen: a manual backup saved on this server, then the ways to
get it to the person (the Backup screen chose the compression already).
Laid out like the Restore picker (screens/files.py): shortcuts, the path
box and the folder tree on the left, what the save will make on the right.

  ╭ 💾 Save database backup ───────────────── ① Folder › ② Saving › ③ Download ╮
  │ [Home] [Backups] [Windows Downloads] [/media] [/mnt] [Up]  ╭ The file ─────╮ │
  │ [📁 New folder] [📂 Open file manager]                       │ Folder        │ │
  │ [/home/ana/backups______________________________________]  │ File name     │ │
  │ ╭ folder tree (folders and the backups already there) ╮    │ Full path     │ │
  │ │ ▾ ana                                                │    │ Compression   │ │
  │ │   ▸ backups                                          │    ├ Disk space ───┤ │
  │ ╰──────────────────────────────────────────────────────╯    │ free / needed │ │
  │                                                             ├ In this folder┤ │
  │                                                             │ 3 backups ... │ │
  │                                                             ├ Then ─────────┤ │
  │                                                             │ download/scp  │ │
  │                                          [💾 Save backup here] [Cancel]      │
  ├──────────────── after the save (left side) ───────────────────────────────────┤
  │ ✅ Backup saved and verified                                                  │
  │ ╭ Download to your computer ╮ [📥 Save to Windows Downloads] / [🌐 Download   │
  │                                in the browser]                                │
  │ ╭ Or download with scp (SSH) ╮ scp ana@192.0.2.10:"..." .   [📋 Copy command] │
  │                                                             [Finish and exit] │
  ╰───────────────────────────────────────────────────────────────────────────────╯

The save is the backup-manual routine, run by the bridge in a task of the
app's loop, so the screen keeps answering while it runs. The copies to the
Windows side are thread workers (copy_file, powershell.exe), which report
to the screen through call_from_thread. The Windows buttons exist only
under WSL2 (save_backup.is_wsl); elsewhere "Download in the browser"
offers the file on a page of this server (screens/web_transfer), for the
browser of the person's computer.
"""

from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from rich.text import Text
from textual.widgets import Button, DirectoryTree, Input, Label, ProgressBar, Static

from .. import save_backup, transfer
from ..i18n import t
from ..opener import reveal_file
from ..widgets.copy import CopyButton
from .dialogs import InputScreen
from .files import BACKUP_SUFFIXES, FilteredTree, PathInput


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


class SaveBackupScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "close", t("Cancel"))]

    def __init__(self, info: dict):
        super().__init__()
        self._home = info.get("real_home") or "/root"
        self._default = save_backup.default_folder(self._home)
        self._user = info.get("real_user") or "root"
        self._host = save_backup.scp_host(info.get("server_ip"))
        self._db = info.get("db_name") or "koha_library"
        self._codec = save_backup.codec_of(info)
        self._estimate = save_backup.size_bytes(info.get("newest_size") or "")
        self._wsl = save_backup.is_wsl()
        self._where = "wsl" if self._wsl else transfer.where()
        self._info = info
        self._file: Path | None = None
        self._scp = ""
        self._busy = False      # saving, or copying to Windows: nothing closes the screen
        self._copying = False
        self._checked: str | None = None   # the path the last Save pressed checked
        self._folder_opened = 0.0
        self._shortcuts = self._places()
        self.accepts_drops = True   # a folder dropped or pasted on the path box (PathInput)

    def _places(self) -> list[tuple[str, Path]]:
        """The shortcut buttons: only the folders that exist (~/backups is
        offered even before the first save: it is created then)."""
        places = [(t("Home"), Path(self._home)), (t("Backups"), self._default)]
        downloads = transfer.downloads_folder(self._where) if self._where in ("wsl", "desktop") else None
        if downloads is not None:
            places.append((t("Windows Downloads") if self._wsl else t("Downloads"), downloads))
        places += [("/media", Path("/media")), ("/mnt", Path("/mnt"))]
        return [(label, path) for label, path in places if path == self._default or path.is_dir()]

    @staticmethod
    def _row(key: str, value_id: str, value: str = "") -> Horizontal:
        return Horizontal(Label(key, classes="sb-key", markup=False),
                          Static(value, id=value_id, classes="sb-val", markup=False), classes="sb-row")

    @staticmethod
    def _card(title: str, card_id: str, *classes: str) -> Vertical:
        card = Vertical(classes=" ".join(("sb-card",) + classes), id=card_id)
        card.border_title = title
        return card

    def compose(self) -> ComposeResult:
        # The tree opens one level up, so the folders next to ~/backups show too.
        start = save_backup.existing_folder(self._default.parent)
        with Vertical(id="sb-box"):
            with Horizontal(id="sb-head"):
                yield Label(t("💾 Save database backup"), classes="dialog-title", id="sb-title", markup=False)
                yield Static("", id="sb-steps")
            with Horizontal(id="sb-body"):
                with Vertical(id="sb-main"):
                    # Step 1: the folder, chosen like in the Restore picker.
                    with Vertical(id="sb-form"):
                        with Horizontal(id="sb-shortcuts"):
                            for i, (label, _path) in enumerate(self._shortcuts):
                                yield Button(label, id=f"sb-go-{i}", classes="sb-go")
                            yield Button(t("Up"), id="sb-up")
                            yield Button(t("📁 New folder"), id="sb-new")
                            if self._where in ("wsl", "desktop"):
                                yield Button(t("📂 Open file manager"), id="sb-open")
                        yield Label(t("Save the backup in this folder of the server:"), classes="sb-prompt",
                                    markup=False)
                        yield PathInput(value=str(self._default), placeholder=str(self._default), id="sb-folder")
                        yield FilteredTree(start, BACKUP_SUFFIXES, id="sb-tree")
                        yield Label("", id="sb-problem", classes="dialog-error", markup=False)
                    # Step 2: the save running.
                    with self._card(t("Saving"), "sb-progress"):
                        yield Label("", id="sb-status", markup=False)
                        yield ProgressBar(total=None, show_eta=False, id="sb-bar")
                        yield self._row(t("Full path"), "sb-target")
                    # Step 3: the ways to take the file to the person's computer.
                    with VerticalScroll(id="sb-done"):
                        yield Label(t("✅ Backup saved and verified"), id="sb-ok", markup=False)
                        with self._card(t("Download to your computer"), "sb-download", "-download"):
                            if self._wsl:
                                yield Static(t("Copies the file from the Linux side to Windows, where you use it."),
                                             classes="sb-hint", markup=False)
                            else:
                                yield Static(t("Opens a page of this server: the browser of your computer "
                                               "downloads the file, no command needed."),
                                             classes="sb-hint", markup=False)
                            with Horizontal(classes="sb-card-buttons"):
                                if self._wsl:
                                    yield Button(t("📥 Save to Windows Downloads"), id="win-downloads",
                                                 variant="success")
                                    yield Button(t("📁 Choose folder in Windows"), id="win-pick")
                                else:
                                    yield Button(t("🌐 Download in the browser"), id="web-download",
                                                 variant="success")
                                if self._where == "desktop":
                                    yield Button(t("📂 Show in file manager"), id="sb-reveal")
                        with self._card(t("Or download with scp (SSH)"), "sb-ssh"):
                            yield Static(t("To copy it to your computer, open Terminal or PowerShell there and "
                                           "paste this command:"), classes="sb-hint", markup=False)
                            with Horizontal(classes="sb-side-row"):
                                yield Static("", id="sb-scp", classes="dialog-command", markup=False)
                                yield CopyButton(command=True, id="copy-scp")
                            yield Static(t("You will be asked for the password of user '${user}'.",
                                           user=self._user), classes="dialog-note sb-note", markup=False)
                        with self._card(t("Good to know"), "sb-tips"):
                            yield Static(t("• The file stays on this server; Finish and exit deletes nothing.\n"
                                           "• Keep a copy off this server too (your computer, a USB drive or the "
                                           "cloud): a copy on the same disk is lost with the disk.\n"
                                           "• To bring it back later: Backup center > Restore database."),
                                         classes="sb-hint", markup=False)
                # The right side: what the save makes, and where.
                with VerticalScroll(id="sb-side"):
                    with self._card(t("The file that will be created"), "sb-preview"):
                        yield self._row(t("Folder"), "sb-pv-folder")
                        yield self._row(t("File name"), "sb-pv-name")
                        yield self._row(t("Full path"), "sb-pv-path")
                        yield self._row(t("Compression"), "sb-pv-codec", save_backup.codec_label(self._codec))
                        yield self._row(t("Size"), "sb-pv-size", "—")
                        yield Static(t("The compression is the one chosen on the Backup screen."),
                                     classes="dialog-note sb-note", markup=False)
                        with Horizontal(classes="sb-card-buttons", id="sb-path-buttons"):
                            yield CopyButton(id="copy-path")
                    with self._card(t("Disk space"), "sb-space"):
                        yield self._row(t("Free"), "sb-free")
                        yield self._row(t("Needed"), "sb-need")
                        yield Static("", id="sb-space-note", classes="sb-hint", markup=False)
                    with self._card(t("Already in this folder"), "sb-there"):
                        yield Static("", id="sb-there-text", markup=False)
                    with self._card(t("After saving"), "sb-then"):
                        yield Static(self._then_text(), classes="sb-hint", markup=False)
            with Horizontal(id="sb-buttons-save", classes="dialog-buttons"):
                yield Button(t("💾 Save backup here"), id="save", variant="primary")
                yield Button(t("Cancel"), id="cancel")
            with Horizontal(id="sb-buttons-done", classes="dialog-buttons"):
                yield Button(t("Finish and exit"), id="done", variant="primary")

    def _then_text(self) -> str:
        if self._wsl:
            way = t("a button copies it to your Windows Downloads, or to a folder you choose in Windows")
        else:
            way = t("a button opens a page of this server where your browser downloads it")
        return t("The backup is checked when it is saved. Then ${way}, and the scp command for another "
                 "computer is ready to copy.", way=way)

    def on_mount(self) -> None:
        self.query_one("#sb-progress").display = False
        self.query_one("#sb-done").display = False
        self.query_one("#sb-buttons-done").display = False
        self.query_one("#sb-problem").display = False
        self.query_one("#sb-path-buttons").display = False
        self._show_step(1)
        self._preview()
        # The name carries the minute of the save: kept current while the screen waits.
        self.set_interval(20, self._preview)
        self.query_one("#sb-folder", Input).focus()

    # --- the header and the right side -------------------------------------
    def _show_step(self, current: int) -> None:
        steps = (t("Folder"), t("Saving"), t("Download"))
        text = Text()
        for n, label in enumerate(steps, 1):
            if n > 1:
                text.append("  ›  ", style="dim")
            mark = "✓" if n < current else "①②③"[n - 1]
            style = "bold reverse" if n == current else ("" if n < current else "dim")
            text.append(f" {mark} {label} ", style=style)
        self.query_one("#sb-steps", Static).update(text)

    def _target_folder(self) -> Path | None:
        raw = self.query_one("#sb-folder", Input).value.strip()
        if not raw:
            return self._default
        path = Path(transfer.dropped_path(raw))
        return path if path.is_absolute() else None

    def _preview(self) -> None:
        if self._file is not None or self._busy:
            return
        folder = self._target_folder()
        name = save_backup.file_name(self._db, self._codec)
        if folder is None:
            self.query_one("#sb-pv-folder", Static).update(t("Use the full path, starting with /."))
            self.query_one("#sb-pv-name", Static).update(name)
            self.query_one("#sb-pv-path", Static).update("—")
            return
        where = f"{folder.as_posix().rstrip('/')}/"
        if not folder.exists():
            where += "  " + t("(it will be created)")
        self.query_one("#sb-pv-folder", Static).update(where)
        self.query_one("#sb-pv-name", Static).update(name)
        self.query_one("#sb-pv-path", Static).update((folder / name).as_posix())
        self._show_folder_facts(folder)

    def _show_folder_facts(self, folder: Path) -> None:
        facts = save_backup.folder_facts(folder)
        free = facts["free"]
        self.query_one("#sb-free", Static).update(transfer.human_size(free) if free is not None else "—")
        need = self._estimate
        self.query_one("#sb-need", Static).update(
            t("about ${size} (the newest backup)", size=transfer.human_size(need)) if need else "—")
        if free is None:
            note = ""
        elif need and free < need * 2:
            note = t("⚠ Little room: the save needs about twice the size of a backup while it is written.")
        else:
            note = t("✓ Enough room on this disk.")
        self.query_one("#sb-space-note", Static).update(note)
        if facts["count"]:
            text = t("${n} backup(s), ${size} in all.\nNewest: ${name}", n=facts["count"],
                     size=transfer.human_size(facts["bytes"]), name=facts["newest"])
        elif folder.is_dir():
            text = t("No backup in this folder yet.")
        else:
            text = t("The folder will be created when the backup is saved.")
        self.query_one("#sb-there-text", Static).update(text)

    def _problem(self, text: str) -> None:
        label = self.query_one("#sb-problem", Label)
        label.update(text)
        label.display = bool(text)

    # --- the folder: box, tree, shortcuts ------------------------------------
    @on(Input.Changed, "#sb-folder")
    def _folder_changed(self, event: Input.Changed) -> None:
        # The message of the last Save stays until the path is changed again.
        if event.value != self._checked:
            self._problem("")
        self._preview()

    def _open(self, folder: Path) -> None:
        """The tree shows folder (or the nearest one above that exists), the
        box says folder."""
        self.query_one("#sb-tree", FilteredTree).path = save_backup.existing_folder(folder)
        self.query_one("#sb-folder", Input).value = str(folder)

    @on(DirectoryTree.DirectorySelected, "#sb-tree")
    def _dir_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        event.stop()
        if not self._busy:
            self.query_one("#sb-folder", Input).value = str(event.path)

    @on(DirectoryTree.FileSelected, "#sb-tree")
    def _file_selected(self, event: DirectoryTree.FileSelected) -> None:
        # A backup already there: its folder is the one meant.
        event.stop()
        if not self._busy:
            self.query_one("#sb-folder", Input).value = str(event.path.parent)

    @on(Button.Pressed, ".sb-go")
    def _go(self, event: Button.Pressed) -> None:
        index = int((event.button.id or "sb-go-0").rsplit("-", 1)[1])
        self._open(self._shortcuts[index][1])

    @on(Button.Pressed, "#sb-up")
    def _up(self) -> None:
        current = self._target_folder() or self._default
        self._open(current.parent)

    @on(Button.Pressed, "#sb-new")
    def _new_folder(self) -> None:
        base = save_backup.existing_folder(self._target_folder() or self._default)

        def check(name: str) -> str:
            name = (name or "").strip()
            if not name or "/" in name or name in (".", ".."):
                return t("Type only the name of the new folder, without /.")
            if (base / name).exists():
                return t("There is already something with that name here.")
            return ""

        def made(name: str | None) -> None:
            if not name:
                return
            target = base / name.strip()
            try:
                target.mkdir(parents=False)
            except OSError as e:
                self._problem(f"{type(e).__name__}: {e}")
                return
            self.query_one("#sb-tree", FilteredTree).reload()
            self._open(target)
            self.app.notify(t("Folder created: ${folder}", folder=str(target)), timeout=5)

        self.app.push_screen(InputScreen(t("📁 New folder"), t("The folder is created inside ${folder}.",
                                                               folder=str(base)),
                                         t("Name of the new folder:"), validate=check), made)

    @on(Button.Pressed, "#sb-open")
    def _open_in_file_manager(self) -> None:
        import time
        now = time.monotonic()
        if now - self._folder_opened < 2.0:
            return
        self._folder_opened = now
        folder = str(save_backup.existing_folder(self._target_folder() or self._default))
        self.app.notify(t("Opening ${folder} in the file manager...", folder=folder), timeout=4)
        self.run_worker(lambda: self._show_folder(folder), thread=True, exclusive=True,
                        group="open-folder", exit_on_error=False)

    def _show_folder(self, folder: str) -> None:
        from ..opener import open_user_folder
        try:
            ok = open_user_folder(folder)
        except Exception:  # noqa: BLE001 - an error here must not close the panel
            ok = False
        if not ok:
            self.app.call_from_thread(self.app.notify, t("No file manager could be opened from here."),
                                      severity="warning")

    def dropped(self, text: str) -> None:
        """A folder dropped on the path box (PathInput): it becomes the folder."""
        path = Path(transfer.dropped_path(text) or "/")
        self._open(path if path.is_dir() or not path.exists() else path.parent)

    # --- step 1: the save -------------------------------------------------
    @on(Button.Pressed, "#save")
    @on(Input.Submitted, "#sb-folder")
    def _start(self) -> None:
        if self._busy:
            return
        self._checked = self.query_one("#sb-folder", Input).value
        folder, problem = save_backup.folder_problem(self._checked, self._default)
        self._problem(t(problem) if problem else "")
        if problem:
            return
        self._busy = True
        self.query_one("#sb-form").display = False
        self.query_one("#sb-progress").display = True
        self.query_one("#sb-then").display = False
        self.query_one("#sb-buttons-save").display = False
        self.query_one("#sb-target", Static).update(
            (folder / save_backup.file_name(self._db, self._codec)).as_posix())
        self._show_step(2)
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
        self.query_one("#sb-then").display = True
        self._show_step(1)
        self._preview()
        self._problem(text)
        self.query_one("#sb-folder", Input).focus()

    def _show_done(self, size: str) -> None:
        self.query_one("#sb-progress").display = False
        self.query_one("#sb-buttons-save").display = False
        self.query_one("#sb-buttons-done").display = True
        self.query_one("#sb-done").display = True
        self._show_step(3)
        self.query_one("#sb-preview").border_title = t("The file saved")
        self.query_one("#sb-pv-folder", Static).update(f"{self._file.parent.as_posix()}/")
        self.query_one("#sb-pv-name", Static).update(self._file.name)
        self.query_one("#sb-pv-path", Static).update(str(self._file))
        self.query_one("#sb-pv-size", Static).update(size or "—")
        self.query_one("#sb-path-buttons").display = True
        self._show_folder_facts(self._file.parent)
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

    @on(Button.Pressed, "#copy-path")
    def _copy_path(self) -> None:
        self.app.copy_to_clipboard(str(self._file or ""))

    @on(Button.Pressed, "#sb-reveal")
    def _show_in_file_manager(self) -> None:
        if self._file is not None and not self.app.env.demo:
            self._reveal()

    @on(Button.Pressed, "#done")
    @on(Button.Pressed, "#cancel")
    def action_close(self) -> None:
        if self._busy:
            self.app.notify(t("Wait until the backup is saved."), severity="warning")
            return
        # Done or Cancel: the file stays on the server either way; nothing is deleted here.
        self.dismiss(None)
