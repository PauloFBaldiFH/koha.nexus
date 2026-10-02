"""PacmanLoader: Pac-Man eating dots while something heavy runs.

The look follows the bash panel's tui_run / tui_progress (a "C"/"c" head
eating dots), drawn large when there is room:

  indeterminate (progress is None)  Pac-Man crosses the row, eating every
                                    pellet, and the row refills behind him.
  determinate (0.0 .. 1.0)          Pac-Man stands at the progress point;
                                    the pellets behind him are eaten.

The animation is a timer on the event loop, so it only stays smooth while
the work itself runs elsewhere: in a worker (tasks.run_with_loader), never
in an event handler. Plain mode (classic Windows console, Linux console)
draws ASCII only; below five rows of height it draws the one-line form.
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

# Facing right; open, half, closed, half.
_ART = {
    False: (
        ("  ▄███▄ ", " █████▀ ", " ███    ", " █████▄ ", "  ▀███▀ "),
        ("  ▄███▄ ", " ██████▀", " █████  ", " ██████▄", "  ▀███▀ "),
        ("  ▄███▄ ", " ███████", " ███████", " ███████", "  ▀███▀ "),
    ),
    True: (
        ("  .###. ", " #####' ", " ###    ", " #####. ", "  '###' "),
        ("  .###. ", " ######'", " #####  ", " ######.", "  '###' "),
        ("  .###. ", " #######", " #######", " #######", "  '###' "),
    ),
}
_CYCLE = (0, 1, 2, 1)
ART_W = 8
ART_H = 5
PELLET_GAP = 3       # a pellet every 3 columns
POWER_EVERY = 5      # every 5th pellet is a power pellet

YELLOW = Style(color="#ffd400", bold=True)
PELLET = Style(color="#ffb8ae")
POWER = Style(color="#ffb8ae", bold=True)
EATEN = Style(color="#3b8f4a")


class PacmanLoader(Widget):
    """A reusable loading animation. `progress` None = unknown duration."""

    DEFAULT_CSS = """
    PacmanLoader {
        height: 5;
        width: 1fr;
        min-width: 16;
    }
    PacmanLoader.-compact {
        height: 1;
    }
    """

    FPS = 15

    progress: reactive[float | None] = reactive(None)
    plain: reactive[bool] = reactive(False)
    compact: reactive[bool] = reactive(False)

    def __init__(self, *, plain: bool = False, compact: bool = False, colors: bool = True,
                 name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name=name, id=id, classes=classes)
        self.set_reactive(PacmanLoader.plain, plain)
        self.set_reactive(PacmanLoader.compact, compact)
        self.use_color = colors
        self.frame = 0       # mouth position, advances every tick
        self.x = 0           # column of Pac-Man in indeterminate mode

    def on_mount(self) -> None:
        self.set_class(self.compact, "-compact")
        self._timer = self.set_interval(1 / self.FPS, self._tick)

    def watch_compact(self, compact: bool) -> None:
        self.set_class(compact, "-compact")

    def pause(self) -> None:
        self._timer.pause()

    def resume(self) -> None:
        self._timer.resume()

    def _tick(self) -> None:
        self.frame += 1
        if self.progress is None:
            self.x += 1
        self.refresh()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def _style(self, style: Style) -> Style:
        return style if self.use_color else Style()

    def _head_x(self, width: int, sprite_w: int) -> int:
        span = max(1, width - sprite_w)
        if self.progress is None:
            return self.x % (span + 1)
        return round(max(0.0, min(1.0, self.progress)) * span)

    def _pellet(self, col: int, power_on: bool) -> tuple[str, Style] | None:
        if col % PELLET_GAP:
            return None
        n = col // PELLET_GAP
        if n % POWER_EVERY == POWER_EVERY - 1:
            return ("o" if self.plain else "●", self._style(POWER)) if power_on else (" ", Style())
        return ("." if self.plain else "•", self._style(PELLET))

    def render(self) -> Text:
        width = max(self.size.width, ART_W + 4)
        if self.compact or self.size.height < ART_H:
            return self._render_line(width)
        return self._render_art(width)

    def _render_line(self, width: int) -> Text:
        head = "C" if self.frame % 2 == 0 else "c"
        x = self._head_x(width, 1)
        done = self.progress is not None
        text = Text(no_wrap=True, overflow="crop")
        text.append(("=" if done else " ") * x, self._style(EATEN))
        text.append(head, self._style(YELLOW))
        for col in range(x + 1, width):
            text.append("." if self.plain else "·", self._style(PELLET))
        return text

    def _render_art(self, width: int) -> Text:
        sprite = _ART[self.plain][_CYCLE[self.frame % len(_CYCLE)]]
        x = self._head_x(width, ART_W)
        power_on = (self.frame // 4) % 2 == 0
        mid = ART_H // 2
        text = Text(no_wrap=True, overflow="crop", end="")
        for row in range(ART_H):
            if row:
                text.append("\n")
            # Behind Pac-Man: eaten (empty); a green trail in determinate mode.
            if row == mid and self.progress is not None:
                text.append("─" * x if not self.plain else "-" * x, self._style(EATEN))
            else:
                text.append(" " * x)
            text.append(sprite[row], self._style(YELLOW))
            ahead = width - x - ART_W
            if row == mid:
                start = x + ART_W
                for col in range(start, start + ahead):
                    pellet = self._pellet(col, power_on)
                    if pellet:
                        text.append(*pellet)
                    else:
                        text.append(" ")
            else:
                text.append(" " * ahead)
        return text
