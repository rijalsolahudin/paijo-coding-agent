"""Paijo: a minimal inline coding agent.

The app runs inline (not in the alternate screen), so everything Rich prints
lands in the terminal scrollback and stays scrollable. prompt_toolkit only owns
the bottom block: the animated "Thinking…" indicator, the current tool status,
the streaming preview and the editable input. All blocking LLM and tool work
happens in :mod:`llm` / :mod:`tools`.
"""

from __future__ import annotations

import asyncio
import shutil

from prompt_toolkit.application import Application, run_in_terminal
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_bindings import KeyBindingsBase
from prompt_toolkit.layout import ConditionalContainer, HSplit, Layout, Window
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.output import Output
from rich.text import Text

from console import console, farewell
from conversation import Conversation
from header import build_header
from input_area import PromptInput
from llm import SETUP_MESSAGE, Agent, LLMError, StreamRunner, TextDelta, ToolEvent
from preview import Preview
from theme import STYLE
from thinking import Thinking
from toolstatus import ToolStatus
from version import __version__

TICK = 0.18
EXIT_COMMANDS = {"/exit", "/quit", ":q"}
BANNER_ROWS = 3
DEFAULT_SIZE = (80, 24)
EMPTY_REPLY = "Balasan kosong dari model."
INTERRUPTED_NOTE = (
    "[diinterupsi setelah menjalankan tool; sebagian perubahan file mungkin "
    "sudah tersimpan — periksa dulu sebelum mengulang]"
)


class PaijoApp:
    """Wires the banner, conversation, indicators and prompt input together."""

    def __init__(
        self,
        *,
        chat: Agent | None = None,
        input: Input | None = None,
        output: Output | None = None,
    ) -> None:
        self.chat = chat if chat is not None else Agent()
        self.conversation = Conversation(console)
        self.input = PromptInput()
        self.thinking = Thinking()
        self.preview = Preview()
        self.tools = ToolStatus()

        self._busy = False
        self._cancel_requested = False
        self._runner: StreamRunner | None = None
        self._spinner: asyncio.Task[None] | None = None

        activity = ConditionalContainer(
            HSplit([self.thinking.container, self.tools.container, self.preview.container]),
            filter=Condition(lambda: self._busy),
        )
        self.layout = Layout(
            HSplit(
                [
                    activity,
                    Window(height=Dimension.exact(1), char=" "),
                    self.input.frame,
                ]
            ),
            focused_element=self.input.window,
        )
        self.application: Application[None] = Application(
            layout=self.layout,
            key_bindings=self._build_key_bindings(),
            style=STYLE,
            full_screen=False,
            input=input,
            output=output,
        )

    @property
    def pending(self) -> bool:
        """True while a turn is being fetched, streamed or executed."""
        return self._busy

    def _build_key_bindings(self) -> KeyBindingsBase:
        kb = KeyBindings()

        @kb.add("enter")
        def _submit(event) -> None:
            # Only submit once the pending turn has finished.
            if self._busy:
                return
            text = self.input.text
            self.input.reset()
            stripped = text.strip()
            if not stripped:
                return
            if stripped in EXIT_COMMANDS:
                event.app.exit()
                return
            event.app.create_background_task(self._run_turn(text))

        @kb.add("escape", "enter")
        def _newline(event) -> None:
            self.input.newline()

        @kb.add("c-c")
        def _cancel(event) -> None:
            if self._busy:
                self._cancel_requested = True
                if self._runner is not None:
                    # Also kills a running command and stops further tool calls.
                    self._runner.cancel()
                self.application.invalidate()
            else:
                self.input.reset()

        @kb.add("c-d", filter=Condition(lambda: self.input.text == ""))
        def _quit(event) -> None:
            event.app.exit()

        return kb

    async def _spin(self) -> None:
        while self.thinking.active:
            await asyncio.sleep(TICK)
            if not self.thinking.active:
                return
            self.thinking.tick()
            self.application.invalidate()

    async def _run_turn(self, text: str) -> None:
        await run_in_terminal(lambda: self.conversation.add_user(text))

        self._busy = True
        self._cancel_requested = False
        reset = getattr(self.chat, "reset_cancel", None)
        if callable(reset):
            reset()
        self.thinking.start()
        self.preview.stop()
        self.tools.clear()
        self.application.invalidate()
        self._spinner = self.application.create_background_task(self._spin())

        items = self.chat.input_items(text)
        runner = StreamRunner(
            lambda: self.chat.stream(items),
            on_cancel=getattr(self.chat, "cancel", None),
        ).start()
        self._runner = runner

        pieces: list[str] = []
        used_tools = False
        failure: LLMError | None = None
        try:
            async for event in runner.events():
                if isinstance(event, ToolEvent):
                    used_tools = True
                    self.thinking.stop()
                    self.tools.update(event.name, event.state)
                    self.application.invalidate()
                    continue
                if isinstance(event, TextDelta):
                    if not pieces:
                        self.thinking.stop()
                        self.preview.start()
                    pieces.append(event.text)
                    self.preview.append(event.text)
                    self.application.invalidate()
        except LLMError as exc:
            failure = exc

        await self._finish_turn(
            text, "".join(pieces), failure, self._cancel_requested, used_tools
        )

    async def _finish_turn(
        self,
        text: str,
        reply: str,
        failure: LLMError | None,
        cancelled: bool,
        used_tools: bool,
    ) -> None:
        self.thinking.stop()
        self.preview.stop()
        self._busy = False
        self._cancel_requested = False
        if self._runner is not None:
            # Only cancel a runner that may still be working. Cancelling a
            # finished one would also cancel the agent and blank out every
            # later turn.
            if cancelled:
                self._runner.cancel()
            self._runner = None
        if self._spinner is not None:
            self._spinner.cancel()
            self._spinner = None
        self.application.invalidate()

        if cancelled:
            # An interrupted turn that already ran tools stays in history: writes
            # are not rolled back, so a retry must be able to see them.
            if used_tools:
                self.chat.note_interruption(text, INTERRUPTED_NOTE)
            await run_in_terminal(lambda: self.conversation.add_cancelled(reply))
        elif failure is not None:
            await run_in_terminal(lambda: self.conversation.add_error(reply, str(failure)))
        elif reply.strip():
            self.chat.commit(text, reply)
            await run_in_terminal(lambda: self.conversation.add_assistant(reply))
        else:
            await run_in_terminal(lambda: self.conversation.add_error(reply, EMPTY_REPLY))

    def _print_banner(self) -> None:
        """Clear the screen, print the banner (and setup hint), pad, then start."""
        console.clear()
        console.print(build_header(__version__))
        extra = 0
        if not self.chat.configured:
            console.print()
            console.print(Text(SETUP_MESSAGE, style="bold red"))
            extra = SETUP_MESSAGE.count("\n") + 2
        rows = self._terminal_rows()
        padding = max(0, rows - BANNER_ROWS - extra - 4 - 1)
        if padding:
            print("\n" * padding, end="", flush=True)

    def _terminal_rows(self) -> int:
        try:
            return self.application.output.get_size().rows
        except Exception:
            return shutil.get_terminal_size(DEFAULT_SIZE).lines

    def run(self) -> None:
        try:
            self.application.run(pre_run=self._print_banner)
        except KeyboardInterrupt:
            pass
        finally:
            close = getattr(self.chat, "close", None)
            if callable(close):
                close()
            farewell()


def main() -> None:
    PaijoApp().run()


if __name__ == "__main__":
    main()
