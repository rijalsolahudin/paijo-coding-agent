"""Animated "Thinking…" indicator shown while waiting for the first chunk.

Kept as a prompt_toolkit container so it renders at the same time as the (still
editable) input. It collapses to zero height when idle.
"""

from prompt_toolkit.filters import Always, Condition
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import ConditionalContainer, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension

FRAMES = ("", ".", "..", "...")


class Thinking:
    """A one-line animated label."""

    def __init__(self) -> None:
        self.active = False
        self._frame = 0
        self.container = ConditionalContainer(
            Window(
                content=FormattedTextControl(self._text),
                height=Dimension.exact(1),
                dont_extend_height=Always(),
            ),
            filter=Condition(lambda: self.active),
        )

    def _text(self) -> FormattedText:
        return FormattedText([("class:thinking", "Thinking" + FRAMES[self._frame])])

    def start(self) -> None:
        self.active = True
        self._frame = 0

    def stop(self) -> None:
        self.active = False

    def tick(self) -> None:
        self._frame = (self._frame + 1) % len(FRAMES)
