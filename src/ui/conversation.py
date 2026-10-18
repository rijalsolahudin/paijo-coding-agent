"""Rich rendering of the conversation, printed to the terminal scrollback.

Static messages only: user turns are printed as a left-aligned green block with a
``❯`` marker and no padding; assistant turns are printed as padded Markdown (one
leading space per line, plain terminal background, no name label). Nothing here
touches prompt_toolkit — the caller prints these through ``run_in_terminal``.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from rich.console import Console
from rich.markdown import Markdown
from rich.padding import Padding
from rich.text import Text

# Terminals have no alpha channel, so "semi transparent" is approximated by
# blending the green over a dark terminal background: #3fb950 at ~60% over #1a1a1a.
USER_BG = "#2f7a3c"
USER_FG = "#ffffff"
USER_MARK_FG = "#1b5a2a"
USER_MARK = "❯ "
USER_INDENT = "  "
USER_PAD = " "

LEAD = " "
NOTICE_STYLE = "grey54"
ERROR_STYLE = "bold red"
CANCELLED_NOTICE = "[dibatalkan]"

TOOL_BADGE_BG = "#3fb950"
TOOL_BADGE_FG = "#0b1f12"
TOOL_FAIL_BG = "#b03a3a"

DIFF_ADDED = "#3fb950"
DIFF_ADDED_BG = "#16301c"
DIFF_REMOVED = "#f85149"
DIFF_REMOVED_BG = "#3a1a1a"
DIFF_DIM = "grey54"
MAX_DIFF_LINES = 20


def format_duration(seconds: float) -> str:
    """Human-ish duration: ``3s``, ``2m 3s``, ``1h 2m``."""
    total = max(0, int(round(seconds)))
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s" if secs else f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m" if minutes else f"{hours}h"


@dataclass
class DiffPreview:
    """Parsed unified diff: counts, path and the rows worth showing."""

    path: str
    additions: int
    removals: int
    rows: list[tuple[int, str, str]]  # (line number, sign, content)

    @property
    def summary(self) -> str:
        parts = []
        if self.additions:
            parts.append(f"{self.additions} addition" + ("" if self.additions == 1 else "s"))
        if self.removals:
            parts.append(f"{self.removals} removal" + ("" if self.removals == 1 else "s"))
        if not parts:
            return f"Updated {self.path}"
        return f"Updated {self.path} with " + " and ".join(parts)


def _parse_diff(diff: str) -> DiffPreview:
    path = ""
    additions = 0
    removals = 0
    rows: list[tuple[int, str, str]] = []
    lineno = 0

    for line in diff.splitlines():
        if line.startswith("--- "):
            path = line[4:].strip()
            continue
        if line.startswith("+++ "):
            continue
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            lineno = int(match.group(1)) if match else 0
            continue
        if not line:
            continue

        sign, content = line[0], line[1:]
        if sign == "+":
            additions += 1
            rows.append((lineno, "+", content))
            lineno += 1
        elif sign == "-":
            removals += 1
            rows.append((lineno, "-", content))
        else:
            rows.append((lineno, " ", content))
            lineno += 1

    return DiffPreview(path, additions, removals, rows)

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
        self.diffs: list[str] = []
        self.tool_calls: list[tuple[str, str, bool]] = []
        self.durations: list[float] = []

    def add_user(self, text: str) -> None:
        self.entries.append(Entry("user", text))
        self.console.print()
        self.console.print(self._user_block(text, self.console.width))

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

    def add_duration(self, seconds: float) -> None:
        """Footer under a finished turn: how long the agent worked on it."""
        self.durations.append(seconds)
        self.console.print()
        self.console.print(Text(f" Worked for {format_duration(seconds)}", style=DIFF_DIM))

    def add_tool(self, name: str, detail: str, ok: bool, output: str = "") -> None:
        """Print a tool badge; for ``edit`` also the summary and diff preview."""
        self.tool_calls.append((name, detail, ok))
        badge_bg = TOOL_BADGE_BG if ok else TOOL_FAIL_BG

        line = Text()
        line.append(f" {name.upper()} ", style=f"bold {TOOL_BADGE_FG} on {badge_bg}")
        if detail:
            line.append(f" [{detail}]", style="bold")
        if name == "read" and ok and output:
            count = sum(1 for row in output.splitlines() if row.strip())
            line.append(f"  {count} lines", style=DIFF_DIM)

        self.console.print()
        self.console.print(line)

        if name == "edit" and ok and output.startswith("--- "):
            self.add_diff(output)
        elif not ok and output:
            self.console.print(Text(f" └ {output.splitlines()[0]}", style=DIFF_REMOVED))

    def add_diff(self, diff: str) -> None:
        """Print the edit summary and a compact, git-coloured diff preview."""
        self.diffs.append(diff)
        parsed = _parse_diff(diff)

        self.console.print(Text(f" └ {parsed.summary}"))

        width = self.console.width
        body = Text()
        for index, (lineno, sign, content) in enumerate(parsed.rows[:MAX_DIFF_LINES]):
            if index:
                body.append("\n")
            prefix = f"   {lineno:>4}  ┊ "
            body.append(prefix, style=DIFF_DIM)
            room = max(1, width - len(prefix))
            text = f"{sign} {content}"
            if sign == "+":
                body.append(text[:room].ljust(room), style=f"{DIFF_ADDED} on {DIFF_ADDED_BG}")
            elif sign == "-":
                body.append(text[:room].ljust(room), style=f"{DIFF_REMOVED} on {DIFF_REMOVED_BG}")
            else:
                body.append(text[:room])

        remaining = len(parsed.rows) - MAX_DIFF_LINES
        if remaining > 0:
            body.append(f"\n   … {remaining} more lines", style=DIFF_DIM)

        self.console.print(body)

    def _print_partial(self, partial: str) -> None:
        if partial.strip():
            self._print_markdown(partial)

    def _print_markdown(self, markdown: str) -> None:
        # Padding pads every rendered line on the left, which is the required
        # leading space, while leaving the terminal background untouched.
        self.console.print(Padding(Markdown(markdown), (0, 0, 0, len(LEAD))))

    @staticmethod
    def _user_block(text: str, width: int) -> Text:
        """A left-aligned green block: one padding cell, then the ``❯`` marker."""
        lines = _wrap(text, width - len(USER_MARK) - 2 * len(USER_PAD))
        body = f"{USER_FG} on {USER_BG}"
        mark = f"{USER_MARK_FG} on {USER_BG}"

        out = Text(no_wrap=True)
        for index, line in enumerate(lines):
            if index:
                out.append("\n")
            out.append(USER_PAD, style=mark)
            out.append(USER_MARK if index == 0 else USER_INDENT, style=mark)
            out.append(line, style=body)
            out.append(USER_PAD, style=body)
        return out
