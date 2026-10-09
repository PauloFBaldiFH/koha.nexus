"""PathPickerScreen: choose a folder (where to save a backup) or a file (the
backup to restore), with the mouse or the keyboard.

  ┌ Title ───────────────────────────────────────────────────────────┐
  │ [Home] [Backups] [/media] [/mnt] [Up]        │ help text          │
  │ path: /root/backups____________________      │ (how to send a     │
  │ ▸ folder tree (only backups in file mode)    │  file to this      │
  │                                              │  server...)        │
  │                                  [Choose] [Cancel]                │
  └──────────────────────────────────────────────────────────────────┘
The path can also be typed or pasted; Enter on it opens a folder or picks
the file. In file mode a file can be dropped on the window: the terminal
pastes its path. Typed, pasted or dropped, the path is cleaned the same way
(transfer.dropped_path: quotes, C:\\..., file://, backslash escapes), and a
name with blanks or parentheses ("BKP_BIBLIOTECA (2).backup") is a path like
any other. A file that is not on this server (the panel used over SSH) gets
the command that sends it here, with its Copy button. A path that cannot be
read (no permission, too long) is said under the box, never raised: an
error in a screen's handler would close the whole panel.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Iterable

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Label, Static

from ..i18n import t
from ..transfer import dropped_path
from .dialogs import CopyValues, MessageScreen

BACKUP_SUFFIXES = (".sql", ".sql.gz", ".gz", ".sql.bz2", ".sql.xz", ".sql.zst", ".backup", ".bkp", ".dump")


def path_kind(path: Path) -> str:
    """"dir", "file", "missing" or "denied", without raising (a path with a
    NUL, too long, or in a folder this user cannot read)."""
    try:
        if path.is_dir():
            return "dir"
        if path.is_file():
            return "file" if os.access(path, os.R_OK) else "denied"
        return "missing"
    except PermissionError:
        return "denied"
    except (OSError, ValueError):
        return "missing"


def typed_path(text: str) -> Path:
    """The path in the box, cleaned as a dropped one ("/" when empty)."""
    return Path(dropped_path(text) or "/")


class PathInput(Input):
    """The path box: a dropped file goes to the screen, not into the text."""

    def _on_paste(self, event: events.Paste) -> None:
        screen = self.screen
        if getattr(screen, "accepts_drops", False):
            event.stop()
            screen.dropped(event.text)
            return
        super()._on_paste(event)


class FilteredTree(DirectoryTree):
    """Hidden entries out; in file mode only folders and the wanted files."""

    def __init__(self, path: str | Path, suffixes: tuple[str, ...] | None, **kwargs):
        self.suffixes = suffixes
        super().__init__(path, **kwargs)

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        keep = []
        for p in paths:
            if p.name.startswith("."):
                continue
            try:
                is_dir = p.is_dir()
            except (OSError, ValueError):
                continue
            if is_dir or self.suffixes is None or p.name.lower().endswith(self.suffixes):
                keep.append(p)
        return keep


class PathPickerScreen(CopyValues, ModalScreen[Path | None]):
    BINDINGS = [Binding("escape", "cancel", t("Cancel")), Binding("backspace", "up", t("Up"), show=False)]

    def __init__(self, title: str, start: str | Path, mode: str = "dir",
                 suffixes: tuple[str, ...] | None = BACKUP_SUFFIXES,
                 shortcuts: list[tuple[str, str]] | None = None, help_text: str = "",
                 commands: list[str] | None = None, send_command: Callable[[str], str] | None = None):
        super().__init__()
        self._title, self._mode, self._help = title, mode, help_text
        self._commands = commands or []
        self._send_command = send_command
        self._values: list[str] = []
        self.accepts_drops = mode == "file"
        self._suffixes = suffixes if mode == "file" else ()
        start_path = Path(start)
        self._start = start_path if path_kind(start_path) == "dir" else Path("/")
        self._shortcuts = [(label, path) for label, path in (shortcuts or []) if path_kind(Path(path)) == "dir"]

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-box"):
            yield Label(self._title, classes="dialog-title", markup=False)
            with Horizontal(id="picker-body"):
                with Vertical(id="picker-main"):
                    with Horizontal(id="picker-shortcuts"):
                        for i, (label, _path) in enumerate(self._shortcuts):
                            yield Button(label, id=f"go-{i}", classes="picker-go")
                        yield Button(t("Up"), id="up", classes="picker-go")
                    if self.accepts_drops:
                        yield Static(t("📥 Drop the file here, or paste its path.") if self._suffixes is None
                                     else t("📥 Drop a .sql or .sql.gz file here, or paste its path."),
                                     id="picker-drop", markup=False)
                    yield PathInput(str(self._start), id="picker-path")
                    yield FilteredTree(self._start, self._suffixes if self._mode == "file" else None,
                                       id="picker-tree")
                    yield Label("", id="picker-error", classes="dialog-error", markup=False)
                if self._help:
                    # Read-only: Tab goes from the tree straight to the buttons.
                    help_box = VerticalScroll(id="picker-help")
                    help_box.can_focus = False
                    with help_box:
                        yield from self.copy_rows(self._commands, command=True)
                        yield Static(self._help, markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("Choose this folder") if self._mode == "dir" else t("Choose this file"),
                             id="choose", variant="primary")
                yield Button(t("Cancel"), id="cancel")

    def on_mount(self) -> None:
        self.query_one("#picker-tree").focus()

    # ------------------------------------------------------------------
    def _open(self, folder: Path) -> None:
        tree = self.query_one("#picker-tree", FilteredTree)
        tree.path = folder
        self.query_one("#picker-path", Input).value = str(folder)
        self.query_one("#picker-error", Label).update("")

    def _wanted(self, path: Path) -> bool:
        """The kind of file this picker is for (any file when no suffixes)."""
        return not self._suffixes or path.name.lower().endswith(self._suffixes)

    def _unreadable(self, kind: str) -> None:
        err = self.query_one("#picker-error", Label)
        if kind == "denied":
            err.update(t("This file cannot be read: no permission to open it."))
        else:
            err.update(t("The file does not exist or cannot be read.\\nNothing was changed.").split("\\n")[0])

    def _choose(self, path: Path) -> None:
        err = self.query_one("#picker-error", Label)
        kind = path_kind(path)
        if self._mode == "dir":
            if kind != "dir":
                err.update(t("Choose a folder."))
                return
        elif kind == "dir":
            self._open(path)
            return
        elif kind != "file":
            self._unreadable(kind)
            return
        self.dismiss(path)

    @on(DirectoryTree.DirectorySelected)
    def _dir_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        event.stop()
        self.query_one("#picker-path", Input).value = str(event.path)

    @on(DirectoryTree.FileSelected)
    def _file_selected(self, event: DirectoryTree.FileSelected) -> None:
        event.stop()
        self.query_one("#picker-path", Input).value = str(event.path)

    @on(Input.Submitted, "#picker-path")
    def _typed(self, event: Input.Submitted) -> None:
        path = typed_path(event.value)
        if str(path) != event.value:
            event.input.value = str(path)
        if path_kind(path) == "dir":
            self._open(path)
        else:
            self._choose(path)

    @on(Button.Pressed, ".picker-go")
    def _go(self, event: Button.Pressed) -> None:
        if event.button.id == "up":
            self.action_up()
            return
        index = int((event.button.id or "go-0").split("-")[1])
        self._open(Path(self._shortcuts[index][1]))

    def action_up(self) -> None:
        if isinstance(self.focused, Input):
            return
        current = Path(self.query_one("#picker-tree", FilteredTree).path)
        self._open(current.parent)

    @on(Button.Pressed, "#choose")
    def _choose_pressed(self) -> None:
        self._choose(typed_path(self.query_one("#picker-path", Input).value))

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)

    # ------------------------------------------------------------------
    # A file dropped on the window (its path pasted by the terminal)
    # ------------------------------------------------------------------
    def on_paste(self, event: events.Paste) -> None:
        if self.accepts_drops and event.text.strip():
            event.stop()
            self.dropped(event.text)

    def dropped(self, text: str) -> None:
        raw = text.strip().splitlines()[0].strip() if text.strip() else ""
        if not raw:
            return
        path = Path(dropped_path(raw) or "/")
        self.query_one("#picker-path", Input).value = str(path)
        err = self.query_one("#picker-error", Label)
        kind = path_kind(path)
        if kind == "dir":
            self._open(path)
            return
        if kind == "file":
            if not self._wanted(path):
                err.update(t("Choose a .sql or .sql.gz file.") if self._suffixes == BACKUP_SUFFIXES
                           else t('Choose a file of this kind: ${kinds}', kinds=", ".join(self._suffixes)))
                return
            self.dismiss(path)
            return
        if kind == "denied":
            self._unreadable(kind)
            return
        if self._send_command:
            self.app.push_screen(MessageScreen(
                self._title, t("That file is not on this server: it is on your computer. "
                               "Send it with the command below, then choose it here."),
                kind="info", command=self._send_command(raw.strip("'\""))))
            return
        err.update(t("The file does not exist or cannot be read.\\nNothing was changed.").split("\\n")[0])
