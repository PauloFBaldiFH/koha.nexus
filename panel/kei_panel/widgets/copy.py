"""CopyButton: "📋 Copy" (or "📋 Copy command" next to a command) that says
"✓ Copied!" for a moment after it is pressed. The copy itself stays with
whoever handles Button.Pressed (app.copy_to_clipboard); the button only
gives the feedback, so every Copy of the panel looks and answers the same."""

from __future__ import annotations

from textual.widgets import Button

from ..i18n import t

COPY = "📋 Copy"
COPY_COMMAND = "📋 Copy command"
COPIED = "✓ Copied!"
FEEDBACK_SECONDS = 2.0


class CopyButton(Button):
    def __init__(self, command: bool = False, **kwargs):
        self._idle = t(COPY_COMMAND if command else COPY)
        super().__init__(self._idle, **kwargs)
        self.add_class("copy-button")
        self._timer = None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # Not stopped: the screen or card above still does the copy.
        self.flash()

    def flash(self) -> None:
        self.label = t(COPIED)
        self.add_class("-copied")
        if self._timer is not None:
            self._timer.stop()
        self._timer = self.set_timer(FEEDBACK_SECONDS, self._back)

    def _back(self) -> None:
        self._timer = None
        self.label = self._idle
        self.remove_class("-copied")
