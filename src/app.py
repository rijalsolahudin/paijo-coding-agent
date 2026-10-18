"""Paijo terminal front-end.

This module is the *only* place that knows about terminals: prompt_toolkit owns
the bottom block (Thinking indicator, tool status, streaming preview and the
editable input) and Rich prints static messages to the scrollback. The engine
itself lives in :mod:`core` and is UI-agnostic, so another front-end (desktop,
web, …) can drive the same session.
"""

from __future__ import annotations

import asyncio
import shutil
import time

from prompt_toolkit.application import Application, run_in_terminal
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.key_bindings import KeyBindingsBase
from prompt_toolkit.layout import ConditionalContainer, HSplit, Layout, Window
from prompt_toolkit.output import Output
from rich.text import Text

from core import Agent, Session, SETUP_MESSAGE, TextDelta, ToolEvent, TurnDone
from ui.console import console, farewell
from ui.conversation import Conversation
from ui.header import build_header
from ui.input_area import PromptInput
from ui.preview import Preview
from ui.theme import STYLE
from ui.thinking import Thinking
from ui.toolstatus import ToolStatus
from version import __version__

TICK = 0.18
EXIT_COMMANDS = {"/exit", "/quit", ":q"}
BANNER_ROWS = 3
DEFAULT_SIZE = (80, 24)
EMPTY_REPLY = "Balasan kosong dari model."


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
        self.session = Session(self.chat)
        self.conversation = Conversation(console)
        self.input = PromptInput()
        self.thinking = Thinking()
        self.preview = Preview()
        self.tools = ToolStatus()

        self._busy = False
        self._spinner: asyncio.Task[None] | None = None

        activity = ConditionalContainer(
            HSplit(
                [
                    # A blank line between the printed user turn and the indicator.
                    Window(height=1, char=" "),
                    self.thinking.container,
                    self.tools.container,
                    self.preview.container,
                ]
            ),
            filter=Condition(lambda: self._busy),
        )
        self.layout = Layout(
            HSplit([activity, self.input.container]),
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

        @kb.add("c-j")
        def _newline(event) -> None:
            # Shift+Enter cannot be reported by a terminal on its own, so it is
            # remapped to send LF ("\n"): that is this binding. See the README.
            self.input.newline()

        @kb.add("c-c")
        def _cancel(event) -> None:
            if self._busy:
                self.session.cancel()
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
        started = time.monotonic()
        await run_in_terminal(lambda: self.conversation.add_user(text))

        self._busy = True
        self.thinking.start()
        self.preview.stop()
        self.tools.clear()
        self.application.invalidate()
        self._spinner = self.application.create_background_task(self._spin())

        try:
            async for event in self.session.send(text):
                if isinstance(event, ToolEvent):
                    await self._on_tool_event(event)
                elif isinstance(event, TextDelta):
                    self._on_text(event.text)
                elif isinstance(event, TurnDone):
                    await self._on_turn_done(event)
                    elapsed = time.monotonic() - started
                    await run_in_terminal(
                        lambda: self.conversation.add_duration(elapsed)
                    )
        finally:
            self.thinking.stop()
            self.preview.stop()
            self._busy = False
            if self._spinner is not None:
                self._spinner.cancel()
                self._spinner = None
            self.application.invalidate()

    async def _on_tool_event(self, event: ToolEvent) -> None:
        self.thinking.stop()
        self.tools.update(event.name, event.state, event.detail)
        self.application.invalidate()
        if event.state != "running":
            await run_in_terminal(
                lambda: self.conversation.add_tool(
                    event.name,
                    event.detail,
                    event.state == "finished",
                    event.output or "",
                )
            )

    def _on_text(self, text: str) -> None:
        if not self.preview.active:
            self.thinking.stop()
            self.preview.start()
        self.preview.append(text)
        self.application.invalidate()

    async def _on_turn_done(self, event: TurnDone) -> None:
        self.thinking.stop()
        self.preview.stop()
        self.application.invalidate()

        if event.status == "cancelled":
            await run_in_terminal(lambda: self.conversation.add_cancelled(event.reply))
        elif event.status == "error":
            await run_in_terminal(
                lambda: self.conversation.add_error(event.reply, event.error or "")
            )
        elif event.status == "empty":
            await run_in_terminal(
                lambda: self.conversation.add_error(event.reply, EMPTY_REPLY)
            )
        else:
            await run_in_terminal(lambda: self.conversation.add_assistant(event.reply))

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
        padding = max(0, rows - BANNER_ROWS - extra - 3 - 1)
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
            self.session.close()
            farewell()


def main() -> None:
    PaijoApp().run()


if __name__ == "__main__":
    main()
