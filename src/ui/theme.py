"""Shared palette and prompt_toolkit style rules for the Paijo interface."""

from prompt_toolkit.styles import Style

INPUT_FG = "#ffffff"
PLACEHOLDER_FG = "#888888"
DIM_FG = "ansibrightblack"
GREEN = "#3fb950"

# Tool badge palette, shared with the Rich scrollback badges (ui/conversation.py).
TOOL_BADGE_BG = GREEN
TOOL_BADGE_FG = "#0b1f12"

STYLE = Style.from_dict(
    {
        # Input: no background, a white top/bottom rule and a green ❯ prefix.
        "input.body": f"fg:{INPUT_FG}",
        "input.prompt": f"fg:{GREEN}",
        "input.rule": f"fg:{INPUT_FG}",
        "input.placeholder": f"fg:{PLACEHOLDER_FG} italic",
        # Pending / streaming indicators.
        "thinking": f"fg:{PLACEHOLDER_FG} italic",
        "tool.running": f"fg:{PLACEHOLDER_FG} italic",
        "tool.finished": f"fg:{GREEN}",
        "tool.failed": "fg:ansired",
        # A sub-agent's "[PLAN]" tag: the same green block as its scrollback badge.
        "tool.agent": f"bold fg:{TOOL_BADGE_FG} bg:{TOOL_BADGE_BG}",
    }
)
