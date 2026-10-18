"""Shared test helpers — no network, no API key."""

from __future__ import annotations

import asyncio
import time

from prompt_toolkit.input import create_pipe_input  # noqa: F401  (re-exported)
from prompt_toolkit.output import DummyOutput

from app import PaijoApp

BOOT = 0.2


class FakeChat:
    """Stands in for :class:`llm.Agent`, replaying scripted events."""

    def __init__(self, events=(), *, delay: float = 0.0, error=None) -> None:
        self.events = list(events)
        self.delay = delay
        self.error = error
        self.history: list[dict] = []
        self.requests: list[list[dict]] = []
        self.interrupted: list[tuple[str, str]] = []
        self.cancelled = False
        self.configured = True

    def input_items(self, user_text: str) -> list[dict]:
        return [*self.history, {"role": "user", "content": user_text}]

    def stream(self, items):
        self.requests.append(list(items))
        if self.cancelled:
            return
        for event in self.events:
            if self.delay:
                time.sleep(self.delay)
            yield event
        if self.error is not None:
            raise self.error

    def commit(self, user_text: str, reply: str) -> None:
        self.history.append({"role": "user", "content": user_text})
        self.history.append(
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": reply}],
            }
        )

    def note_interruption(self, user_text: str, note: str) -> None:
        self.interrupted.append((user_text, note))

    def cancel(self) -> None:
        self.cancelled = True

    def reset_cancel(self) -> None:
        self.cancelled = False

    def close(self) -> None:
        pass


async def start_app(chat: FakeChat, pipe) -> tuple[PaijoApp, asyncio.Task]:
    app = PaijoApp(chat=chat, input=pipe, output=DummyOutput())
    runner = asyncio.create_task(app.application.run_async())
    await asyncio.sleep(BOOT)
    return app, runner


async def stop_app(app: PaijoApp, runner: asyncio.Task) -> None:
    app.application.exit()
    await runner


def roles(app: PaijoApp) -> list[str]:
    return [entry.role for entry in app.conversation.entries]
