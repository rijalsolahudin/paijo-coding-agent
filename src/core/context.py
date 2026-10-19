"""Ambient context shared between the agent loop and the tools it dispatches.

The Responses API loop is the only thing that knows a tool call's depth and the
cancellation signal, but a tool such as ``task`` needs them too. Rather than
widening the ``dispatch`` signature, the loop publishes an :class:`AgentContext`
through a :class:`contextvars.ContextVar` right before it runs a call. Everything
runs on the same worker thread, so the value set there is the value a tool reads.
"""

from __future__ import annotations

import contextvars
import threading
from dataclasses import dataclass

# Sub-agents may not spawn their own sub-agents.
MAX_DEPTH = 1


@dataclass(frozen=True)
class AgentContext:
    """What a running tool call needs to know about the agent that invoked it."""

    depth: int
    cancel: threading.Event
    client: object | None


CURRENT: contextvars.ContextVar[AgentContext | None] = contextvars.ContextVar(
    "paijo_agent_context", default=None
)
