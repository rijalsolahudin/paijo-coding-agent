"""The engine session, driven directly without any terminal UI."""

import asyncio

from core import LLMError, Session, TextDelta, ToolEvent
from support import FakeChat


def test_session_streams_events_then_reports_ok():
    async def scenario() -> None:
        chat = FakeChat([TextDelta("ha"), TextDelta("lo")])
        session = Session(chat)

        events = [event async for event in session.send("hi")]

        assert [type(event).__name__ for event in events] == [
            "TextDelta",
            "TextDelta",
            "TurnDone",
        ]
        assert events[-1].status == "ok"
        assert events[-1].reply == "halo"
        assert chat.history[-1]["content"][0]["text"] == "halo"

    asyncio.run(scenario())


def test_session_does_not_commit_a_failed_turn():
    async def scenario() -> None:
        chat = FakeChat([TextDelta("par")], error=LLMError("koneksi putus"))
        session = Session(chat)

        events = [event async for event in session.send("hi")]

        assert events[-1].status == "error"
        assert events[-1].error == "koneksi putus"
        assert chat.history == []

    asyncio.run(scenario())


def test_session_keeps_an_interrupted_turn_only_when_tools_ran():
    async def scenario() -> None:
        chat = FakeChat(
            [
                ToolEvent("write", "running", detail="a.txt"),
                ToolEvent("write", "finished", "ok", "a.txt"),
                TextDelta("..."),
            ],
            delay=0.4,
        )
        session = Session(chat)

        async for event in session.send("tulis file"):
            if isinstance(event, ToolEvent) and event.state == "finished":
                session.cancel()

        assert len(chat.interrupted) == 1
        assert chat.interrupted[0][0] == "tulis file"
        assert "diinterupsi" in chat.interrupted[0][1]

    asyncio.run(scenario())


def test_session_cancel_without_tools_keeps_the_turn_out_of_history():
    async def scenario() -> None:
        chat = FakeChat([TextDelta("sebagian")], delay=0.5)
        session = Session(chat)

        async def consume() -> None:
            async for _ in session.send("halo"):
                session.cancel()

        await consume()

        assert chat.history == []
        assert chat.interrupted == []

    asyncio.run(scenario())
