"""Startup banner: agent name, version and hotkey hints."""

from rich import box
from rich.panel import Panel
from rich.text import Text

HOTKEYS = "Enter send · Alt+Enter newline · Ctrl+C cancel · Ctrl+D quit"


def build_header(version: str) -> Panel:
    """Build the framed banner that is printed once at startup."""
    text = Text()
    text.append(" Paijo ", style="bold white")
    text.append(f"v{version} ", style="green")
    text.append("· ", style="green")
    text.append(HOTKEYS, style="grey54")
    return Panel(text, box=box.SQUARE, border_style="green", padding=(0, 0))
