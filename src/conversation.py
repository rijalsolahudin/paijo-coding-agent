"""Rich rendering of the conversation, printed to the terminal scrollback.

Static messages only: user turns are printed as a right-aligned bubble with a
dark background; assistant turns are printed as padded Markdown (one leading
space per line, plain terminal background, no name label). Nothing here touches
prompt_toolkit — the caller prints these through ``run_in_terminal``.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from rich.cells import cell_len
from rich.console import Console
from rich.markdown import Markdown
from rich.padding import Padding
from rich.text import Text

BUBBLE_BG = "#333333"
BUBBLE_FG = "#dddddd"
PAD_H = 1
PAD_V = 1
RIGHT_MARGIN = 2

LEAD = " "
NOTICE_STYLE = "grey54"
ERROR_STYLE = "bold red"
CANCELLED_NOTICE = "[dibatalkan]"

_WRAP_CONSOLE = Console(
    file=io.StringIO(),
    force_terminal=True,
    color_system="truecolor",
    _environ={},
)


def _wrap(text: str, width: int) -> list[str]:
    if not text:
        return [""]
    lines = Text(text).wrap(_WRAP_CONSOLE, max(8, width), overflow="fold")
    return [line.plain for line in lines] or [""]


@dataclass
class Entry:
    role: str
    text: str


class Conversation:
    """Keeps the transcript and prints each entry with Rich."""

    def __init__(self, console: Console) -> None:
        self.console = console
        self.entries: list[Entry] = []
        self.notices: list[str] = []

    def add_user(self, text: str) -> None:
        self.entries.append(Entry("user", text))
        self.console.print()
        self.console.print(self._bubble(text, self.console.width))

    def add_assistant(self, markdown: str) -> None:
        self.entries.append(Entry("assistant", markdown))
        self.console.print()
        self._print_markdown(markdown)

    def add_cancelled(self, partial: str) -> None:
        """Show whatever streamed before the user cancelled, plus a note."""
        self.notices.append(CANCELLED_NOTICE)
        self.console.print()
        self._print_partial(partial)
        self.console.print(Text(LEAD + CANCELLED_NOTICE, style=NOTICE_STYLE))

    def add_error(self, partial: str, message: str) -> None:
        """Show whatever streamed before the failure, plus a readable error."""
        self.notices.append(message)
        self.console.print()
        self._print_partial(partial)
        self.console.print(Text(LEAD + message, style=ERROR_STYLE))

    def _print_partial(self, partial: str) -> None:
        if partial.strip():
            self._print_markdown(partial)

    def _print_markdown(self, markdown: str) -> None:
        # Padding pads every rendered line on the left, which is the required
        # leading space, while leaving the terminal background untouched.
        self.console.print(Padding(Markdown(markdown), (0, 0, 0, len(LEAD))))

    @staticmethod
    def _bubble(text: str, width: int) -> Text:
        """Build a right-aligned block of ``text`` on a dark background."""
        segments = _wrap(text, width - RIGHT_MARGIN - 2 * PAD_H)
        content = max(cell_len(segment) for segment in segments)
        block = content + 2 * PAD_H
        gutter = " " * max(0, width - RIGHT_MARGIN - block)
        style = f"{BUBBLE_FG} on {BUBBLE_BG}"

        rows = [" " * block] * PAD_V
        rows += [
            " " * PAD_H + segment + " " * (content - cell_len(segment)) + " " * PAD_H
            for segment in segments
        ]
        rows += [" " * block] * PAD_V

        out = Text(no_wrap=True)
        for index, row in enumerate(rows):
            if index:
                out.append("\n")
            out.append(gutter)
            out.append(row, style=style)
        return out
