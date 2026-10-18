"""Paijo's four tools: read, write, edit and bash.

The typed functions are the single source of truth for schema, argument
validation and execution. aisuite's ``Tools`` helper turns them into tool
definitions; the agent loop dispatches calls itself (see :mod:`llm`) so it can
report per-call status and match Responses API call ids.
"""

from __future__ import annotations

from collections.abc import Callable

from aisuite.utils.tools import Tools

from tools.bash import bash, terminate_active
from tools.edit import edit
from tools.read import read
from tools.utils import ToolError
from tools.write import write

TOOLS: tuple[Callable[..., str], ...] = (read, write, edit, bash)

__all__ = [
    "TOOLS",
    "ToolError",
    "bash",
    "build_tools",
    "dispatch",
    "edit",
    "read",
    "schemas",
    "terminate_active",
    "write",
]


def build_tools() -> Tools:
    """Register the tools with aisuite so it can describe them."""
    return Tools(list(TOOLS))


def schemas() -> list[dict]:
    """Tool definitions in aisuite's (Chat Completions) shape."""
    return build_tools().tools(format="openai")


def dispatch(name: str, arguments: dict) -> str:
    """Run one tool call by name. Errors propagate; the caller reports them."""
    functions = {function.__name__: function for function in TOOLS}
    function = functions.get(name)
    if function is None:
        raise ToolError(f"unknown tool {name!r}")
    return function(**arguments)
