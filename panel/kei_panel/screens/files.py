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
the file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Label, Static

from ..i18n import t

BACKUP_SUFFIXES = (".sql", ".sql.gz", ".gz")


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
            except OSError:
                continue
            if is_dir or self.suffixes is None or p.name.lower().endswith(self.suffixes):
                keep.append(p)
        return keep


class PathPickerScreen(ModalScreen[Path | None]):
    BINDINGS = [Binding("escape", "cancel", t("Cancel")), Binding("backspace", "up", t("Up"), show=False)]

    def __init__(self, title: str, start: str | Path, mode: str = "dir",
                 suffixes: tuple[str, ...] | None = BACKUP_SUFFIXES,
                 shortcuts: list[tuple[str, str]] | None = None, help_text: str = ""):
        super().__init__()
        self._title, self._mode, self._help = title, mode, help_text
        self._suffixes = suffixes if mode == "file" else ()
        start_path = Path(start)
        self._start = start_path if start_path.is_dir() else Path("/")
        self._shortcuts = [(label, path) for label, path in (shortcuts or []) if Path(path).is_dir()]

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-box"):
            yield Label(self._title, classes="dialog-title")
            with Horizontal(id="picker-body"):
                with Vertical(id="picker-main"):
                    with Horizontal(id="picker-shortcuts"):
                        for i, (label, _path) in enumerate(self._shortcuts):
                            yield Button(label, id=f"go-{i}", classes="picker-go")
                        yield Button(t("Up"), id="up", classes="picker-go")
                    yield Input(str(self._start), id="picker-path")
                    yield FilteredTree(self._start, self._suffixes if self._mode == "file" else None,
                                       id="picker-tree")
                    yield Label("", id="picker-error", classes="dialog-error")
                if self._help:
                    # Read-only: Tab goes from the tree straight to the buttons.
                    help_box = VerticalScroll(id="picker-help")
                    help_box.can_focus = False
                    with help_box:
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

    def _choose(self, path: Path) -> None:
        err = self.query_one("#picker-error", Label)
        if self._mode == "dir":
            if not path.is_dir():
                err.update(t("Choose a folder."))
                return
        elif path.is_dir():
            self._open(path)
            return
        elif not path.is_file():
            err.update(t("The file does not exist or cannot be read.\\nNothing was changed.").split("\\n")[0])
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
        path = Path(event.value.strip() or "/").expanduser()
        if path.is_dir() and self._mode == "file":
            self._open(path)
        elif path.is_dir():
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
        self._choose(Path(self.query_one("#picker-path", Input).value.strip() or "/").expanduser())

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)
