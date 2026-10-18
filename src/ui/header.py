"""Startup banner: agent name, version and hotkey hints."""

from rich import box
from rich.panel import Panel
from rich.text import Text

from ui.theme import GREEN

HOTKEYS = "Enter send · Shift+Enter newline · Ctrl+C cancel · Ctrl+D quit"


def build_header(version: str) -> Panel:
    """Build the framed banner that is printed once at startup."""
    text = Text()
    text.append(" Paijo ", style="bold white")
    text.append(f"v{version} ", style=GREEN)
    text.append("· ", style=GREEN)
    text.append(HOTKEYS, style="grey54")
    return Panel(text, box=box.SQUARE, border_style=GREEN, padding=(0, 0))
