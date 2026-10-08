"""The progress bar of tasks whose progress is known (Pac-Man is for the
waits of unknown length). Textual's own bar, with the percentage; on the
classic Windows console and the Linux console (plain glyphs) it is drawn
with ASCII, as Pac-Man is."""

from __future__ import annotations

from textual.renderables.bar import Bar as BarRenderable
from textual.widgets import ProgressBar


class AsciiBarRenderable(BarRenderable):
    HALF_BAR_LEFT = "-"
    BAR = "="
    HALF_BAR_RIGHT = "-"


class AsciiProgressBar(ProgressBar):
    BAR_RENDERABLE = AsciiBarRenderable


def task_progress_bar(plain: bool, **kwargs) -> ProgressBar:
    cls = AsciiProgressBar if plain else ProgressBar
    return cls(total=100, show_eta=False, **kwargs)
