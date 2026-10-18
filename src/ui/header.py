"""Startup banner: the PAIJO wordmark plus a few dim detail lines."""

from rich.text import Text

from ui.theme import DIM_FG, GREEN

WORDMARK = [
    "██████╗  █████╗ ██╗     ██╗ ██████╗",
    "██╔══██╗██╔══██╗██║     ██║██╔═══██╗",
    "██████╔╝███████║██║     ██║██║   ██║",
    "██╔═══╝ ██╔══██║██║██   ██║██║   ██║",
    "██║     ██║  ██║██║╚█████╔╝╚██████╔╝",
    "╚═╝     ╚═╝  ╚═╝╚═╝ ╚════╝  ╚═════╝",
]


def build_header(version: str, *, model: str, cwd: str) -> Text:
    """Build the banner printed once at startup: wordmark + detail lines."""
    lines = [Text(line, style=f"bold {GREEN}") for line in WORDMARK]
    lines.append(Text())
    for detail in (f"Paijo v{version}", f"models: {model}", cwd):
        lines.append(Text(f"# {detail}", style=DIM_FG))
    return Text("\n").join(lines)
