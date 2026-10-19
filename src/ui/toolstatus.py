"""Compact one-line status for the tool the agent is currently running."""

import time

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
# A sub-agent label ("[PLAN]") renders as the same green block as its badge; the
# rest of the line keeps the normal tool style.
AGENT_STYLE = "class:tool.agent"


class ToolStatus:
    """Shows e.g. ``bash running`` above the input, and collapses when idle."""

    def __init__(self) -> None:
        self.name = ""
        self.state = ""
        self.detail = ""
        self.active = False
        self.elapsed = 0.0
        self._started: float | None = None
        self.container = ConditionalContainer(
            Window(
                content=FormattedTextControl(self._text),
                height=Dimension.exact(1),
                dont_extend_height=Always(),
            ),
            filter=Condition(lambda: self.active),
        )

    def _text(self) -> FormattedText:
        if self.state == "running" and self._started is not None:
            elapsed = time.monotonic() - self._started
        else:
            elapsed = self.elapsed
        suffix = f" {int(elapsed)}s" if elapsed >= 1 else ""
        detail = f" {self.detail}" if self.detail else ""
        state_style = STYLES.get(self.state, "")
        if self.name.startswith("["):
            tail = f"{self.detail} {self.state}{suffix}".strip()
            return FormattedText([(AGENT_STYLE, f" {self.name} "), (state_style, tail)])
        return FormattedText([(state_style, f" {self.name}{detail} {self.state}{suffix}")])

    def update(self, name: str, state: str, detail: str = "") -> None:
        self.name = name
        self.state = state
        self.detail = detail
        if state == "running":
            self._started = time.monotonic()
            self.elapsed = 0.0
        elif self._started is not None:
            self.elapsed = time.monotonic() - self._started
        self.active = True

    def clear(self) -> None:
        self.active = False
