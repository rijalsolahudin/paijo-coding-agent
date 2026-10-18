"""Shared palette and prompt_toolkit style rules for the Paijo interface."""

from prompt_toolkit.styles import Style

INPUT_BG = "#393939"
INPUT_FG = "#ffffff"
PLACEHOLDER_FG = "#888888"
DIM_FG = "ansibrightblack"
GREEN = "#3fb950"

STYLE = Style.from_dict(
    {
        # Input frame: border is painted in the same #393939 as the block, so it
        # reads as blank padding rather than a visible box.
        "frame.border": f"fg:{INPUT_BG} bg:{INPUT_BG}",
        "input.body": f"fg:{INPUT_FG} bg:{INPUT_BG}",
        "input.prompt": f"fg:{GREEN} bold bg:{INPUT_BG}",
        "input.placeholder": f"fg:{PLACEHOLDER_FG} italic bg:{INPUT_BG}",
        # Pending / streaming indicators.
        "thinking": f"fg:{PLACEHOLDER_FG} italic",
        "tool.running": f"fg:{PLACEHOLDER_FG} italic",
        "tool.finished": f"fg:{GREEN}",
        "tool.failed": "fg:ansired",
    }
)
