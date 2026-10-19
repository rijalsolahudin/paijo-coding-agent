"""`task` tool: delegate a self-contained subtask to a fresh-context sub-agent."""

from __future__ import annotations

from tools.utils import ToolError, ToolOutput


def task(prompt: str, description: str, subagent_type: str = "general") -> ToolOutput:
    """Delegate one self-contained subtask to a fresh-context sub-agent.

    The sub-agent runs in its own context and returns only its final answer. Use
    it for work that is self-contained, exploratory, or worth isolating from this
    conversation; trivial single-step work is cheaper to do directly.

    Args:
        prompt: Full, standalone instructions for the sub-agent.
        description: A short (3-5 word) label shown in the UI.
        subagent_type: One of ``general``, ``explore`` or ``plan``.
    """
    # Imported here, not at module load: core.agent imports tools, so importing
    # core at the top of a tool would be a cycle. Deferring it breaks that.
    from core.agent import LLMError
    from core.context import CURRENT, MAX_DEPTH
    from core.subagent import SUBAGENTS, SubAgent

    if subagent_type not in SUBAGENTS:
        options = ", ".join(SUBAGENTS)
        raise ToolError(f"unknown subagent_type {subagent_type!r}; use one of {options}")

    context = CURRENT.get()
    if context is None:
        raise ToolError("task can only run from inside the agent")
    if context.depth >= MAX_DEPTH:
        raise ToolError(f"sub-agents cannot spawn further sub-agents (max depth {MAX_DEPTH})")

    try:
        text = SubAgent(
            SUBAGENTS[subagent_type],
            client=context.client,
            cancel=context.cancel,
            depth=context.depth + 1,
        ).run(prompt)
    except LLMError as exc:
        raise ToolError(str(exc)) from exc

    return ToolOutput(text if text.strip() else "(sub-agent produced no output)")
