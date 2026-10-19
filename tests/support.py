"""Shared test helpers — no network, no API key."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

from prompt_toolkit.input import create_pipe_input  # noqa: F401  (re-exported)
from prompt_toolkit.output import DummyOutput

from app import PaijoApp
from core import Agent

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
        self.model = "test-model"

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


# -- Responses API fakes ------------------------------------------------------
# A scripted stand-in for the OpenAI client: each ``responses.create`` call pops
# the next scripted batch of SSE events. Shared by the agent-loop and sub-agent
# tests, so neither needs a real network.


def delta(text):
    return SimpleNamespace(type="response.output_text.delta", delta=text)


def refusal(text):
    return SimpleNamespace(type="response.refusal.delta", delta=text)


def completed(*output):
    return SimpleNamespace(type="response.completed", response=SimpleNamespace(output=list(output)))


def failed(status="failed", code=None):
    return SimpleNamespace(
        type="response.failed",
        response=SimpleNamespace(status=status, error=SimpleNamespace(code=code)),
    )


def function_call(name, arguments, call_id):
    return SimpleNamespace(type="function_call", name=name, arguments=arguments, call_id=call_id)


def reasoning(item_id="rs_1"):
    return SimpleNamespace(type="reasoning", id=item_id, encrypted_content="encrypted")


def message_item(text):
    return SimpleNamespace(
        type="message", role="assistant", content=[SimpleNamespace(type="output_text", text=text)]
    )


class FakeStream:
    def __init__(self, events):
        self.events = events
        self.closed = False

    def __iter__(self):
        yield from self.events

    def close(self):
        self.closed = True


class FakeResponses:
    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = []
        self.streams = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        script = self.scripts.pop(0)
        if isinstance(script, Exception):
            raise script
        stream = FakeStream(script)
        self.streams.append(stream)
        return stream


class FakeClient:
    def __init__(self, scripts):
        self.responses = FakeResponses(scripts)
        self.closed = False

    def close(self):
        self.closed = True


def make_agent(scripts, **kwargs):
    client = FakeClient(scripts)
    return Agent(api_key="test-key", client=client, **kwargs), client
