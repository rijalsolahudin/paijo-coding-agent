"""End-to-end behaviour of the inline agent UI (LLM fully faked)."""

import asyncio

from prompt_toolkit.input import create_pipe_input

from core import LLMError, TextDelta, ToolEvent
from support import FakeChat, roles, start_app, stop_app


def test_streamed_deltas_reach_the_preview_then_commit():
    async def scenario() -> None:
        chat = FakeChat([TextDelta("Hel"), TextDelta("lo"), TextDelta(" world")], delay=0.15)
        with create_pipe_input() as pipe:
            app, runner = await start_app(chat, pipe)

            pipe.send_text("halo\r")
            await asyncio.sleep(0.35)
            assert app.pending is True
            assert app.preview.active is True
            assert app.preview.text.startswith("Hel")

            await asyncio.sleep(0.8)
            assert app.pending is False
            assert roles(app) == ["user", "assistant"]
            assert app.conversation.entries[-1].text == "Hello world"
            assert chat.history[-1] == {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "Hello world"}],
            }

            await stop_app(app, runner)

    asyncio.run(scenario())


def test_tool_status_is_shown_above_the_input():
    async def scenario() -> None:
        chat = FakeChat(
            [
                ToolEvent("bash", "running", detail="pytest -q"),
                ToolEvent("bash", "finished", "ok", "pytest -q"),
                TextDelta("selesai"),
            ],
            delay=0.2,
        )
        with create_pipe_input() as pipe:
            app, runner = await start_app(chat, pipe)

            pipe.send_text("jalankan tes\r")
            await asyncio.sleep(0.3)
            assert app.tools.active is True
            assert app.tools.name == "bash"
            assert app.tools.state == "running"
            assert app.tools.detail == "pytest -q"

            await asyncio.sleep(0.4)
            assert app.tools.state == "finished"

            await asyncio.sleep(0.5)
            assert app.pending is False
            assert roles(app) == ["user", "assistant"]
            assert app.conversation.tool_calls == [("bash", "pytest -q", True)]

            await stop_app(app, runner)

    asyncio.run(scenario())


def test_successful_turn_does_not_cancel_the_agent():
    async def scenario() -> None:
        chat = FakeChat([TextDelta("oke")])
        with create_pipe_input() as pipe:
            app, runner = await start_app(chat, pipe)

            pipe.send_text("satu\r")
            await asyncio.sleep(0.6)

            assert chat.cancelled is False

            await stop_app(app, runner)

    asyncio.run(scenario())


def test_every_turn_produces_an_answer():
    async def scenario() -> None:
        chat = FakeChat([TextDelta("jawaban")])
        with create_pipe_input() as pipe:
            app, runner = await start_app(chat, pipe)

            for message in ("satu", "dua", "tiga"):
                pipe.send_text(f"{message}\r")
                await asyncio.sleep(0.5)

            assert roles(app) == [
                "user",
                "assistant",
                "user",
                "assistant",
                "user",
                "assistant",
            ]
            assert app.conversation.notices == []

            await stop_app(app, runner)

    asyncio.run(scenario())


def test_history_is_forwarded_on_the_next_turn():
    async def scenario() -> None:
        chat = FakeChat([TextDelta("oke")])
        with create_pipe_input() as pipe:
            app, runner = await start_app(chat, pipe)

            pipe.send_text("pertama\r")
            await asyncio.sleep(0.6)
            pipe.send_text("kedua\r")
            await asyncio.sleep(0.6)

            second = chat.requests[-1]
            assert second[0] == {"role": "user", "content": "pertama"}
            assert second[1] == {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "oke"}],
            }
            assert second[-1] == {"role": "user", "content": "kedua"}

            await stop_app(app, runner)

    asyncio.run(scenario())


def test_ctrl_c_stops_the_stream_shows_partial_and_keeps_draft():
    async def scenario() -> None:
        chat = FakeChat([TextDelta("sebagian"), TextDelta(" jawaban")], delay=0.4)
        with create_pipe_input() as pipe:
            app, runner = await start_app(chat, pipe)

            pipe.send_text("halo\r")
            await asyncio.sleep(0.5)
            pipe.send_text("draft")
            await asyncio.sleep(0.1)
            pipe.send_text("\x03")  # Ctrl+C
            await asyncio.sleep(0.4)

            assert app.pending is False
            assert app.preview.active is False
            assert roles(app) == ["user"]  # no tools ran -> turn not kept
            assert app.input.text == "draft"  # draft preserved
            assert chat.history == []
            assert chat.interrupted == []
            assert app.conversation.notices == ["[dibatalkan]"]

            await stop_app(app, runner)

    asyncio.run(scenario())


def test_cancel_after_tools_keeps_the_turn_with_an_interruption_note():
    async def scenario() -> None:
        chat = FakeChat(
            [ToolEvent("write", "running"), ToolEvent("write", "finished"), TextDelta("...")],
            delay=0.5,
        )
        with create_pipe_input() as pipe:
            app, runner = await start_app(chat, pipe)

            pipe.send_text("tulis file\r")
            await asyncio.sleep(0.7)  # tool already finished
            pipe.send_text("\x03")
            await asyncio.sleep(0.4)

            assert app.pending is False
            assert len(chat.interrupted) == 1
            user_text, note = chat.interrupted[0]
            assert user_text == "tulis file"
            assert "diinterupsi" in note

            await stop_app(app, runner)

    asyncio.run(scenario())


def test_api_error_is_reported_and_not_committed():
    async def scenario() -> None:
        chat = FakeChat([TextDelta("sebagian")], error=LLMError("Saldo habis (429)."))
        with create_pipe_input() as pipe:
            app, runner = await start_app(chat, pipe)

            pipe.send_text("halo\r")
            await asyncio.sleep(0.6)

            assert app.pending is False
            assert roles(app) == ["user"]
            assert chat.history == []
            assert app.conversation.notices == ["Saldo habis (429)."]

            await stop_app(app, runner)

    asyncio.run(scenario())


def test_enter_is_ignored_while_a_turn_is_pending():
    async def scenario() -> None:
        chat = FakeChat([TextDelta("jawaban")], delay=0.4)
        with create_pipe_input() as pipe:
            app, runner = await start_app(chat, pipe)

            pipe.send_text("pertama\r")
            await asyncio.sleep(0.15)
            pipe.send_text("kedua\r")
            await asyncio.sleep(1.0)

            assert roles(app) == ["user", "assistant"]
            assert chat.requests[0][-1]["content"] == "pertama"
            assert app.input.text == "kedua"

            await stop_app(app, runner)

    asyncio.run(scenario())


def test_shift_enter_remap_inserts_a_newline():
    async def scenario() -> None:
        chat = FakeChat([TextDelta("oke")])
        with create_pipe_input() as pipe:
            app, runner = await start_app(chat, pipe)

            # A terminal remap for Shift+Enter sends LF, which is what we bind.
            pipe.send_text("baris satu\nbaris dua\r")
            await asyncio.sleep(0.6)

            assert app.conversation.entries[0].text == "baris satu\nbaris dua"

            await stop_app(app, runner)

    asyncio.run(scenario())


def test_edit_diff_is_shown_in_the_scrollback():
    async def scenario() -> None:
        diff = "--- a/f.txt\n+++ b/f.txt\n@@ -1 +1 @@\n-old\n+new\n"
        chat = FakeChat(
            [
                ToolEvent("edit", "running"),
                ToolEvent("edit", "finished", diff),
                TextDelta("selesai"),
            ]
        )
        with create_pipe_input() as pipe:
            app, runner = await start_app(chat, pipe)

            pipe.send_text("ganti baris\r")
            await asyncio.sleep(0.6)

            assert app.conversation.diffs == [diff]

            await stop_app(app, runner)

    asyncio.run(scenario())


def test_failed_edit_does_not_print_a_diff():
    async def scenario() -> None:
        chat = FakeChat(
            [
                ToolEvent("edit", "running"),
                ToolEvent("edit", "failed", "error: old_text was not found"),
                TextDelta("gagal"),
            ]
        )
        with create_pipe_input() as pipe:
            app, runner = await start_app(chat, pipe)

            pipe.send_text("ganti baris\r")
            await asyncio.sleep(0.6)

            assert app.conversation.diffs == []

            await stop_app(app, runner)

    asyncio.run(scenario())


def test_turn_duration_is_recorded():
    async def scenario() -> None:
        chat = FakeChat([TextDelta("oke")])
        with create_pipe_input() as pipe:
            app, runner = await start_app(chat, pipe)

            pipe.send_text("halo\r")
            await asyncio.sleep(0.6)

            assert len(app.conversation.durations) == 1
            assert app.conversation.durations[0] >= 0

            await stop_app(app, runner)

    asyncio.run(scenario())


def test_blank_input_is_not_submitted():
    async def scenario() -> None:
        chat = FakeChat([TextDelta("nggak kepakai")])
        with create_pipe_input() as pipe:
            app, runner = await start_app(chat, pipe)

            pipe.send_text("   \r")
            await asyncio.sleep(0.3)

            assert roles(app) == []
            assert chat.requests == []

            await stop_app(app, runner)

    asyncio.run(scenario())
