"""PacmanLoader: a one-line progress bar with Pac-Man eating pellets.

The look of Arch Linux's pacman with ILoveCandy in pacman.conf (and of the
bash panel's tui_run / tui_progress):

  [--------c o  o  o  o  o  o ]

  determinate (0.0 .. 1.0)          Pac-Man stands at the progress point;
                                    the pellets behind him are eaten (-).
  indeterminate (progress is None)  Pac-Man crosses the bar, eating every
                                    pellet, and the bar refills behind him.

The animation is a timer on the event loop, so it only stays smooth while
the work itself runs elsewhere: in a worker (tasks.run_with_loader), never
in an event handler. It is always ASCII, so it draws the same on the
classic Windows console and the Linux console.
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

PELLET_GAP = 3       # a pellet every 3 columns, as in pacman's ILoveCandy

YELLOW = Style(color="#ffd400", bold=True)
PELLET = Style(color="#ffb8ae")
EATEN = Style(color="#6c7086")
BRACKET = Style(dim=True)


class PacmanLoader(Widget):
    """A reusable loading bar. `progress` None = unknown duration."""

    DEFAULT_CSS = """
    PacmanLoader {
        height: 1;
        width: 1fr;
        min-width: 12;
    }
    """

    FPS = 10

    progress: reactive[float | None] = reactive(None)

    def __init__(self, *, plain: bool = False, compact: bool = True, colors: bool = True,
                 name: str | None = None, id: str | None = None, classes: str | None = None):
        # plain / compact: kept for callers; the bar is always one ASCII line.
        super().__init__(name=name, id=id, classes=classes)
        self.use_color = colors
        self.frame = 0       # mouth: open on even frames
        self.x = 0           # column of Pac-Man in indeterminate mode

    def on_mount(self) -> None:
        self._timer = self.set_interval(1 / self.FPS, self._tick)

    def pause(self) -> None:
        self._timer.pause()

    def resume(self) -> None:
        self._timer.resume()

    def _tick(self) -> None:
        self.frame += 1
        if self.progress is None:
            self.x += 1
        self.refresh()

    def _style(self, style: Style) -> Style:
        return style if self.use_color else Style()

    def head_x(self, inner: int) -> int:
        """Pac-Man's column inside the brackets."""
        span = max(1, inner - 1)
        if self.progress is None:
            return self.x % (span + 1)
        return round(max(0.0, min(1.0, self.progress)) * span)

    def render(self) -> Text:
        return self.line(max(self.size.width, 12))

    def line(self, width: int) -> Text:
        inner = width - 2
        x = self.head_x(inner)
        text = Text(no_wrap=True, overflow="crop", end="")
        text.append("[", self._style(BRACKET))
        text.append("-" * x, self._style(EATEN))
        text.append("C" if self.frame % 2 == 0 else "c", self._style(YELLOW))
        for col in range(x + 1, inner):
            text.append("o" if col % PELLET_GAP == 0 else " ", self._style(PELLET))
        text.append("]", self._style(BRACKET))
        return text
