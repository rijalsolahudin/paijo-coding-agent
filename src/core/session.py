"""UI-agnostic turn driver.

``Session`` owns one user turn: it starts the streaming runner, forwards model
events, keeps the partial reply, decides whether the turn is committed to
history, and reports the outcome. Nothing here imports prompt_toolkit or Rich, so
any front-end — terminal, desktop or web — can drive the same engine.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from core.agent import Agent, Event, LLMError, StreamRunner, TextDelta, ToolEvent

INTERRUPTED_NOTE = (
    "[diinterupsi setelah menjalankan tool; sebagian perubahan file mungkin "
    "sudah tersimpan — periksa dulu sebelum mengulang]"
)


@dataclass(frozen=True)
class TurnDone:
    """Final event of a turn; the front-end decides how to render it."""

    reply: str
    status: str  # "ok" | "cancelled" | "error" | "empty"
    error: str | None = None


class Session:
    """Drives one turn at a time against an :class:`Agent`."""

    def __init__(self, agent: Agent | None = None) -> None:
        self.agent = agent if agent is not None else Agent()
        self._runner: StreamRunner | None = None
        self._cancel_requested = False

    async def send(self, text: str) -> AsyncIterator[Event | TurnDone]:
        """Yield model events for ``text``, then exactly one :class:`TurnDone`."""
        self.agent.reset_cancel()
        self._cancel_requested = False

        items = self.agent.input_items(text)
        runner = StreamRunner(
            lambda: self.agent.stream(items),
            on_cancel=self.agent.cancel,
        ).start()
        self._runner = runner

        pieces: list[str] = []
        used_tools = False
        failure: str | None = None
        try:
            async for event in runner.events():
                if isinstance(event, ToolEvent):
                    used_tools = True
                elif isinstance(event, TextDelta):
                    pieces.append(event.text)
                yield event
        except LLMError as exc:
            failure = str(exc)

        cancelled = self._cancel_requested
        self._cancel_requested = False
        self._runner = None
        reply = "".join(pieces)

        if cancelled:
            runner.cancel()
            # Finished writes are not rolled back, so keep the turn in history.
            if used_tools:
                self.agent.note_interruption(text, INTERRUPTED_NOTE)
            yield TurnDone(reply, "cancelled")
        elif failure is not None:
            yield TurnDone(reply, "error", failure)
        elif reply.strip():
            self.agent.commit(text, reply)
            yield TurnDone(reply, "ok")
        else:
            yield TurnDone(reply, "empty")

    def cancel(self) -> None:
        """Stop the current turn: no further events, running command killed."""
        self._cancel_requested = True
        self.agent.cancel()
        if self._runner is not None:
            self._runner.cancel()

    def close(self) -> None:
        self.agent.close()
