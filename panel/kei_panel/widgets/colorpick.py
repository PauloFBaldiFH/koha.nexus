"""ColorPicker: a colour chosen on three bars (hue, saturation, lightness)
instead of typing a code like #2563eb.

The hex field stays (its id is the one the screen reads), with a swatch of
the colour next to it; moving a bar writes the field, typing a valid code
moves the bars. Each bar is drawn with the colours it leads to, so the
saturation bar goes from grey to the pure colour and the lightness bar from
black through the colour to white. Bars move with ←/→ (PageUp/PageDown,
Home/End), a click or a drag.
"""

from __future__ import annotations

import colorsys
import re

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import MouseDown, MouseMove, MouseUp
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Label, Static

HEX = re.compile(r"#[0-9a-fA-F]{6}")


def hex_to_hsl(value: str) -> tuple[int, int, int] | None:
    """'#2563eb' -> (hue 0-359, saturation 0-100, lightness 0-100)."""
    if not HEX.fullmatch(value or ""):
        return None
    r, g, b = (int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, lum, s = colorsys.rgb_to_hls(r, g, b)
    return round(h * 360) % 360, round(s * 100), round(lum * 100)


def hsl_to_hex(h: int, s: int, lum: int) -> str:
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, lum / 100, s / 100)
    return "#{:02x}{:02x}{:02x}".format(*(round(c * 255) for c in (r, g, b)))


class GradientBar(Widget, can_focus=True):
    DEFAULT_CSS = """
    GradientBar {
        width: 1fr;
        height: 2;
        margin: 0 0 1 0;
    }
    GradientBar:focus {
        text-style: bold;
    }
    """
    BINDINGS = [
        Binding("left", "move(-1)", "−", show=False),
        Binding("right", "move(1)", "+", show=False),
        Binding("pageup", "move(-10)", show=False),
        Binding("pagedown", "move(10)", show=False),
        Binding("home", "edge(0)", show=False),
        Binding("end", "edge(1)", show=False),
    ]

    value = reactive(0)

    class Changed(Message):
        def __init__(self, bar: "GradientBar", value: int):
            super().__init__()
            self.bar, self.value = bar, value

        @property
        def control(self) -> "GradientBar":
            return self.bar

    def __init__(self, kind: str, hi: int, value: int, picker: "ColorPicker", **kwargs):
        super().__init__(**kwargs)
        self.kind, self.hi, self.picker = kind, hi, picker
        self._dragging = False
        self.set_reactive(GradientBar.value, self.validate_value(value))

    def validate_value(self, value) -> int:
        try:
            value = int(round(float(value)))
        except (TypeError, ValueError):
            value = 0
        return max(0, min(self.hi, value))

    def watch_value(self, old: int, new: int) -> None:
        if old != new:
            self.post_message(self.Changed(self, new))

    def colour_at(self, frac: float) -> str:
        h, s, lum = self.picker.hsl()
        if self.kind == "h":
            return hsl_to_hex(round(frac * 359), 100, 50)
        if self.kind == "s":
            return hsl_to_hex(h, round(frac * 100), lum)
        return hsl_to_hex(h, s, round(frac * 100))

    def render(self) -> Text:
        width = max(5, self.content_region.width or self.size.width)
        pos = round(self.value / max(1, self.hi) * (width - 1))
        knob_bg = self.colour_at(pos / max(1, width - 1))
        r, g, b = (int(knob_bg[i:i + 2], 16) for i in (1, 3, 5))
        knob_fg = "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else "#ffffff"
        line = Text()
        for x in range(width):
            colour = self.colour_at(x / max(1, width - 1))
            if x == pos:
                line.append("┃", style=f"bold {knob_fg} on {colour}")
            else:
                line.append(" ", style=f"on {colour}")
        out = line.copy()
        out.append("\n")
        out.append_text(line)
        return out

    def action_move(self, steps: int) -> None:
        self.value = self.validate_value(self.value + steps)

    def action_edge(self, end: int) -> None:
        self.value = self.hi if end else 0

    def _at(self, x: int) -> None:
        width = max(5, self.content_region.width or self.size.width)
        self.value = self.validate_value(x / max(1, width - 1) * self.hi)

    def on_mouse_down(self, event: MouseDown) -> None:
        self.focus()
        self._dragging = True
        self.capture_mouse()
        self._at(event.x)

    def on_mouse_move(self, event: MouseMove) -> None:
        if self._dragging:
            self._at(event.x)

    def on_mouse_up(self, event: MouseUp) -> None:
        if self._dragging:
            self._dragging = False
            self.release_mouse()


class ColorPicker(Vertical):
    """The hex field (id input_id) with a swatch, and the three bars."""

    DEFAULT_CSS = """
    ColorPicker {
        height: auto;
    }
    ColorPicker .cp-row {
        height: auto;
    }
    ColorPicker .cp-swatch {
        width: 8;
        height: 3;
        margin-right: 1;
        border: round $panel-lighten-2;
    }
    ColorPicker Input {
        width: 14;
    }
    ColorPicker .cp-label {
        width: 20;
        color: $text-muted;
    }
    ColorPicker .cp-value {
        width: 6;
        padding-left: 1;
        color: $text-muted;
    }
    """

    def __init__(self, label: str, value: str, input_id: str, bar_labels: tuple[str, str, str], **kwargs):
        super().__init__(**kwargs)
        self._label, self._value, self._input_id = label, value, input_id
        self._bar_labels = bar_labels
        self._syncing = False
        self._hsl = hex_to_hsl(value) or (220, 80, 50)

    def hsl(self) -> tuple[int, int, int]:
        return self._hsl

    def compose(self) -> ComposeResult:
        h, s, lum = self._hsl
        with Horizontal(classes="form-row cp-row"):
            yield Label(self._label, classes="form-label")
            yield Static("", classes="cp-swatch")
            yield Input(self._value, id=self._input_id, max_length=7)
        for kind, hi, value, label in (("h", 359, h, self._bar_labels[0]), ("s", 100, s, self._bar_labels[1]),
                                       ("l", 100, lum, self._bar_labels[2])):
            with Horizontal(classes="cp-row"):
                yield Label(label, classes="cp-label")
                yield GradientBar(kind, hi, value, self, classes=f"cp-bar cp-{kind}")
                yield Label(str(value), classes=f"cp-value cp-v-{kind}")

    def on_mount(self) -> None:
        self._paint()

    def _paint(self) -> None:
        colour = hsl_to_hex(*self._hsl)
        self.query_one(".cp-swatch", Static).styles.background = colour
        for bar in self.query(GradientBar):
            bar.refresh()
            self.query_one(f".cp-v-{bar.kind}", Label).update(str(bar.value))

    def on_gradient_bar_changed(self, event: GradientBar.Changed) -> None:
        event.stop()
        h, s, lum = (self.query_one(f".cp-{k}", GradientBar).value for k in "hsl")
        if (h, s, lum) == self._hsl:
            # The bars only followed a code typed in the field: keep it as typed.
            self._paint()
            return
        self._hsl = (h, s, lum)
        self._syncing = True
        try:
            self.query_one(f"#{self._input_id}", Input).value = hsl_to_hex(h, s, lum)
        finally:
            self._syncing = False
        self._paint()

    def on_input_changed(self, event: Input.Changed) -> None:
        # Not stopped: the screen still hears its field change.
        if self._syncing or event.input.id != self._input_id:
            return
        value = event.value.strip().lower()
        hsl = hex_to_hsl(value)
        # Our own write from the bars comes back here too: it must not round
        # the bars (black would also lose the hue and saturation chosen).
        if not hsl or value == hsl_to_hex(*self._hsl):
            return
        self._hsl = hsl
        for kind, value in zip("hsl", hsl):
            self.query_one(f".cp-{kind}", GradientBar).value = value
        self._paint()
