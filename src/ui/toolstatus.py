"""Compact one-line status for the tool the agent is currently running."""

from prompt_toolkit.filters import Always, Condition
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import ConditionalContainer, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension

STYLES = {
    "running": "class:tool.running",
    "finished": "class:tool.finished",
    "failed": "class:tool.failed",
}


class ToolStatus:
    """Shows e.g. ``bash running`` above the input, and collapses when idle."""

    def __init__(self) -> None:
        self.name = ""
        self.state = ""
        self.detail = ""
        self.active = False
        self.container = ConditionalContainer(
            Window(
                content=FormattedTextControl(self._text),
                height=Dimension.exact(1),
                dont_extend_height=Always(),
            ),
            filter=Condition(lambda: self.active),
        )

    def _text(self) -> FormattedText:
        detail = f" {self.detail}" if self.detail else ""
        return FormattedText(
            [(STYLES.get(self.state, ""), f" {self.name}{detail} {self.state}")]
        )

    def update(self, name: str, state: str, detail: str = "") -> None:
        self.name = name
        self.state = state
        self.detail = detail
        self.active = True

    def clear(self) -> None:
        self.active = False
