"""A diagnostics folder (config.sh --export-diagnostics) read inside the
panel: a summary first, then each file of the folder, errors in red.

The folder only holds redacted logs and command output (see the
installer's kei_export_diagnostics), so showing it is safe; the files are
read here, nothing is run.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList, RichLog
from textual.widgets.option_list import Option
from rich.text import Text

from ..i18n import t
from .logtail import _BAD, style_line

# Where the panel's "Export diagnostics" saves (KEI_DIAG_DIR in the installer).
DIAG_DIR = Path("/var/log/koha-easy-install/diagnostics")
PREFIX = "koha-diagnostics-"
SUMMARY = "@summary"
MAX_BYTES = 512 * 1024      # the end of a bigger file is shown
# The files the export writes, in reading order; logs/ come after them.
ORDER = ("README.txt", "status.json", "system.txt", "services.txt")


def list_exports(base: Path = DIAG_DIR) -> list[Path]:
    """The saved diagnostics folders, newest first."""
    try:
        found = [p for p in base.iterdir() if p.is_dir() and p.name.startswith(PREFIX)]
    except OSError:
        return []
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def export_files(folder: Path) -> list[Path]:
    """The files of a diagnostics folder: the export's own first, then logs/."""
    first = [folder / name for name in ORDER if (folder / name).is_file()]
    try:
        logs = sorted(p for p in (folder / "logs").iterdir() if p.is_file())
    except OSError:
        logs = []
    rest = sorted(p for p in folder.glob("*") if p.is_file() and p not in first)
    return first + rest + logs


def read_text(path: Path, limit: int = MAX_BYTES) -> str:
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - limit))
            data = fh.read()
    except OSError as exc:
        return f"{path}: {exc.strerror}"
    text = data.decode("utf-8", "replace")
    return text.split("\n", 1)[-1] if size > limit else text


def error_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if _BAD.search(line))


def _human(n: object) -> str:
    try:
        size = float(n)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "-"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
        size /= 1024
    return "-"


def summary(folder: Path) -> list[str]:
    """What a person checks first: the state from status.json and how many
    error lines each file has."""
    lines = [folder.name, ""]
    try:
        s = json.loads((folder / "status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        s = None
    if isinstance(s, dict):
        when = s.get("generated_at")
        if isinstance(when, int) and when > 0:
            lines.append(f"{t('Exported')}: {time.strftime('%Y-%m-%d %H:%M', time.localtime(when))}")
        lines.append(f"koha.nexus {s.get('panel_version', '?')} · {s.get('platform', '')} · "
                     f"{t('State')}: {s.get('state', '?')}")
        http = s.get("http") or {}
        lines.append(f"{t('Staff / OPAC')}: HTTP {http.get('staff', '-')} / {http.get('opac', '-')}")
        svcs = s.get("services") or {}
        if svcs:
            down = [f"{k} ({v})" for k, v in svcs.items() if v != "active"]
            lines.append(f"{t('Services')}: " + (", ".join(down) if down else t("all running")))
        b = s.get("backup") or {}
        if b.get("last_file"):
            lines.append(f"{t('Last backup')}: {b.get('last_file')} ({b.get('last_result', '-')})")
        d, m = s.get("disk") or {}, s.get("memory") or {}
        lines.append(f"{t('Disk free')}: {_human(d.get('free'))} / {_human(d.get('total'))} · "
                     f"{t('Memory available')}: {_human(m.get('available'))} / {_human(m.get('total'))}")
    else:
        lines.append(t("status.json is missing or unreadable."))
    lines += ["", t("Lines with errors in each file:")]
    for path in export_files(folder):
        if path.name in ("README.txt", "status.json"):
            continue
        n = error_count(read_text(path))
        lines.append(f"  {n:>5}  {path.relative_to(folder)}")
    return lines


class DiagnosticsScreen(ModalScreen[None]):
    """One diagnostics folder: its files on the left, the chosen one on the right."""

    BINDINGS = [Binding("escape", "close", t("Back"))]

    def __init__(self, folder: str | Path, can_open: bool = True):
        super().__init__()
        self._folder = Path(folder)
        self._can_open = can_open

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog -wide -log -diag"):
            yield Label(t("Diagnostics"), classes="dialog-title")
            yield Label(str(self._folder), classes="dialog-note", markup=False)
            with Horizontal(id="diag-body"):
                options = [Option(t("Summary"), id=SUMMARY)]
                options += [Option(str(p.relative_to(self._folder)), id=str(p)) for p in export_files(self._folder)]
                yield OptionList(*options, id="diag-files")
                yield RichLog(classes="dialog-log -tall", id="diag-text", wrap=True, markup=False,
                              max_lines=20000)
            with Horizontal(classes="dialog-buttons"):
                if self._can_open:
                    yield Button(t("Open folder"), id="open-folder")
                yield Button(t("Copy path"), id="copy-path")
                yield Button(t("Back"), id="back", variant="primary")

    def on_mount(self) -> None:
        files = self.query_one("#diag-files", OptionList)
        files.highlighted = 0
        files.focus()
        # After the first layout: RichLog wraps at the width it has when written.
        self.call_after_refresh(self.show, SUMMARY)

    def show(self, key: str) -> None:
        log = self.query_one("#diag-text", RichLog)
        log.clear()
        if key == SUMMARY:
            for line in summary(self._folder):
                log.write(Text(line))
        else:
            for line in read_text(Path(key)).splitlines():
                log.write(style_line(line))
        log.scroll_home(animate=False)

    @on(OptionList.OptionHighlighted, "#diag-files")
    def _pick(self, event: OptionList.OptionHighlighted) -> None:
        if event.option.id:
            self.show(event.option.id)

    @on(Button.Pressed, "#open-folder")
    def _open(self) -> None:
        from ..opener import open_user_folder
        if not open_user_folder(str(self._folder)):
            self.app.notify(t("This computer has no file manager for the panel to open."), severity="warning")

    @on(Button.Pressed, "#copy-path")
    def _copy(self) -> None:
        self.app.copy_to_clipboard(str(self._folder))

    @on(Button.Pressed, "#back")
    def action_close(self) -> None:
        self.dismiss(None)
