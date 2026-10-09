"""A one-line ticker: text that does not fit its box scrolls sideways.

Text that fits is drawn as it is. Text that is too long is cut at the box
edge with "…" while the ticker is still; while it runs (the card is hovered
or focused) it slides one cell at a time, stops for a moment at the start
and at the end so both can be read, then starts over. Only a running ticker
has a timer, and it only repaints when the visible window moves.
"""

from __future__ import annotations

from rich.cells import cell_len
from rich.text import Text
from textual.widget import Widget

from ..glyphs import steady

STEP = 0.15   # seconds per cell (about 7 cells a second)
HOLD = 10     # steps the text stays still at the start and at the end


def cell_window(text: str, start: int, width: int) -> str:
    """The cells start..start+width of text, padded to exactly width cells.
    A wide character cut in half by either edge becomes a space."""
    out: list[str] = []
    pos = used = 0
    for ch in text:
        w = cell_len(ch)
        if pos + w <= start:
            pos += w
            continue
        if pos < start:            # wide character cut by the left edge
            out.append(" " * (pos + w - start))
            used += pos + w - start
        elif used + w > width:     # ... or by the right edge
            break
        else:
            out.append(ch)
            used += w
        pos += w
        if used >= width:
            break
    return "".join(out) + " " * max(0, width - used)


def cell_head(text: str, width: int) -> str:
    """text cut to width cells with "…" at the end."""
    return cell_window(text, 0, width - 1).rstrip() + "…" if width > 0 else ""


class Marquee(Widget):
    """One line of text that scrolls when it does not fit (see the module)."""

    DEFAULT_CSS = "Marquee { height: auto; width: 1fr; }"

    def __init__(self, text: str = "", **kwargs):
        super().__init__(**kwargs)
        self._text = steady(text)
        self._shift = 0
        self._hold = HOLD
        self._scrolling = False
        self._ticker = None

    @property
    def text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = steady(text)
        self._shift, self._hold = 0, HOLD
        self.refresh(layout=True)

    @property
    def overflow(self) -> int:
        """How many cells the text is longer than the box (0 = it fits)."""
        return max(0, cell_len(self._text) - self.content_size.width)

    def get_content_height(self, container, viewport, width: int) -> int:
        return 1

    def render(self) -> Text:
        width = self.content_size.width
        if width <= 0:
            return Text("")
        if not self.overflow:
            line = self._text
        elif self._scrolling:
            line = cell_window(self._text, self._shift, width)
        else:
            line = cell_head(self._text, width)
        return Text(line, no_wrap=True, overflow="crop", end="")

    def run(self, on: bool) -> None:
        """Start (hovered or focused card) or stop the ticker."""
        on = on and self.overflow > 0
        if on == self._scrolling:
            return
        self._scrolling = on
        self._shift, self._hold = 0, HOLD
        if on:
            if self._ticker is None:
                self._ticker = self.set_interval(STEP, self._step)
            else:
                self._ticker.resume()
        elif self._ticker is not None:
            self._ticker.pause()
        self.refresh()

    def _step(self) -> None:
        if not self._scrolling:
            return
        if self._hold:
            self._hold -= 1
            if self._hold == 0 and self._shift >= self.overflow:
                self._shift = 0          # back to the start, then rest there
                self._hold = HOLD
                self.refresh()
            return
        end = self.overflow
        if end == 0:                     # the box grew: nothing to scroll
            self.run(False)
            return
        self._shift = min(self._shift + 1, end)
        if self._shift == end:
            self._hold = HOLD
        self.refresh()

    def on_resize(self) -> None:
        self._shift = min(self._shift, self.overflow)
        self.refresh()

