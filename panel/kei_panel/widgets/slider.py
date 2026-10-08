"""Slider: a number in a range, moved with ←/→ (Home/End) or a click.

Textual has no slider; the OPAC appearance screen needs a few (blur,
opacity, corner radius, carousel speed). One line: the bar, the knob and
the value with its unit.
"""

from __future__ import annotations

from textual.binding import Binding
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget


class Slider(Widget, can_focus=True):
    DEFAULT_CSS = """
    Slider {
        width: 1fr;
        height: 3;
        padding: 1 1;
        color: $text-muted;
    }
    Slider:focus {
        color: $text;
        text-style: bold;
    }
    """
    BINDINGS = [
        Binding("left", "move(-1)", "−", show=False),
        Binding("right", "move(1)", "+", show=False),
        Binding("pageup", "move(-5)", show=False),
        Binding("pagedown", "move(5)", show=False),
        Binding("home", "edge(0)", show=False),
        Binding("end", "edge(1)", show=False),
    ]

    value = reactive(0)

    class Changed(Message):
        def __init__(self, slider: "Slider", value: int):
            super().__init__()
            self.slider, self.value = slider, value

        @property
        def control(self) -> "Slider":
            return self.slider

    def __init__(self, lo: int, hi: int, value: int, step: int = 1, unit: str = "", **kwargs):
        super().__init__(**kwargs)
        self.lo, self.hi, self.step, self.unit = lo, hi, max(1, step), unit
        self.set_reactive(Slider.value, self.validate_value(value))

    def validate_value(self, value) -> int:
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = self.lo
        value = self.lo + round((value - self.lo) / self.step) * self.step
        return max(self.lo, min(self.hi, value))

    def watch_value(self, old: int, new: int) -> None:
        if old != new:
            self.post_message(self.Changed(self, new))

    def label(self) -> str:
        return f" {self.value}{self.unit}"

    def bar_width(self) -> int:
        width = self.content_region.width or self.size.width
        return max(5, width - len(f" {self.hi}{self.unit}") - 1)

    def render(self) -> str:
        bar = self.bar_width()
        span = max(1, self.hi - self.lo)
        pos = round((self.value - self.lo) / span * (bar - 1))
        return "━" * pos + "●" + "─" * (bar - pos - 1) + self.label()

    def action_move(self, steps: int) -> None:
        self.value = self.validate_value(self.value + steps * self.step)

    def action_edge(self, end: int) -> None:
        self.value = self.hi if end else self.lo

    def on_click(self, event: Click) -> None:
        bar = self.bar_width()
        x = event.x - self.styles.padding.left
        if 0 <= x < bar:
            self.value = self.validate_value(self.lo + x / max(1, bar - 1) * (self.hi - self.lo))
        self.focus()
