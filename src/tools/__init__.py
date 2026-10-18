"""Paijo's four tools: read, write, edit and bash.

The typed functions are the single source of truth for schema, argument
validation and execution. aisuite's ``Tools`` helper turns them into tool
definitions; the agent loop dispatches calls itself (see :mod:`llm`) so it can
report per-call status and match Responses API call ids.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable

from aisuite.utils.tools import Tools

from tools.bash import bash, terminate_active
from tools.edit import edit
from tools.read import read
from tools.utils import ToolError, ToolOutput
from tools.write import write

TOOLS: tuple[Callable[..., str | ToolOutput], ...] = (read, write, edit, bash)

__all__ = [
    "TOOLS",
    "ToolError",
    "ToolOutput",
    "bash",
    "build_tools",
    "dispatch",
    "edit",
    "read",
    "schemas",
    "summarize",
    "terminate_active",
    "validate_arguments",
    "write",
]

_FUNCTIONS: dict[str, Callable[..., str]] = {function.__name__: function for function in TOOLS}


def validate_arguments(name: str, arguments: dict) -> None:
    """Raise an actionable :class:`ToolError` for bad arguments.

    The message goes straight back to the model, so it names the argument it got
    wrong and the ones the tool actually accepts.
    """
    function = _FUNCTIONS.get(name)
    if function is None:
        raise ToolError(f"unknown tool {name!r}")

    parameters = inspect.signature(function).parameters

    unexpected = [key for key in arguments if key not in parameters]
    if unexpected:
        expected = ", ".join(parameters)
        raise ToolError(
            f"{name}() got unexpected argument(s): {', '.join(unexpected)}. Expected: {expected}"
        )

    missing = [
        key
        for key, param in parameters.items()
        if param.default is inspect.Parameter.empty and key not in arguments
    ]
    if missing:
        raise ToolError(f"{name}() is missing required argument(s): {', '.join(missing)}")


def summarize(name: str, arguments: str) -> str:
    """A short, human-visible hint of what a tool call is about to do."""
    try:
        data = json.loads(arguments) if arguments.strip() else {}
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict):
        return ""
    if name == "bash":
        return " ".join(str(data.get("command", "")).split())[:60]
    return str(data.get("path", ""))


def build_tools() -> Tools:
    """Register the tools with aisuite so it can describe them."""
    return Tools(list(TOOLS))


def schemas() -> list[dict]:
    """Tool definitions in aisuite's (Chat Completions) shape."""
    return build_tools().tools(format="openai")


def dispatch(name: str, arguments: dict) -> str | ToolOutput:
    """Run one tool call by name. Errors propagate; the caller reports them."""
    validate_arguments(name, arguments)
    return _FUNCTIONS[name](**arguments)
