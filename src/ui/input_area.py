"""Single-line prompt input framed by a top and a bottom rule.

The block is exactly three rows: a top rule, the editing line (with a green ``❯``
prefix), and a bottom rule. There is no background fill and no extra padding.
"""

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Always, Condition
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import HSplit, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.processors import AfterInput, ConditionalProcessor

PROMPT_PREFIX = "❯ "
PLACEHOLDER = "Ask Paijo to do something…"
RULE = "─"


class PromptInput:
    """A three-row prompt input backed by a multiline buffer."""

    def __init__(self) -> None:
        self.buffer = Buffer(multiline=True)
        empty = Condition(lambda: self.buffer.text == "")

        control = BufferControl(
            buffer=self.buffer,
            input_processors=[
                ConditionalProcessor(
                    AfterInput(PLACEHOLDER, style="class:input.placeholder"),
                    empty,
                )
            ],
        )
        self.window = Window(
            content=control,
            height=Dimension.exact(1),
            dont_extend_height=Always(),
            wrap_lines=False,
            style="class:input.body",
        )
        prompt = Window(
            content=FormattedTextControl(
                FormattedText([("class:input.prompt", PROMPT_PREFIX)])
            ),
            width=2,
            height=Dimension.exact(1),
            dont_extend_height=Always(),
            style="class:input.body",
        )
        body = VSplit(
            [prompt, self.window],
            height=Dimension.exact(1),
            style="class:input.body",
        )
        self.container = HSplit(
            [
                Window(
                    height=Dimension.exact(1),
                    char=RULE,
                    dont_extend_height=Always(),
                    style="class:input.rule",
                ),
                body,
                Window(
                    height=Dimension.exact(1),
                    char=RULE,
                    dont_extend_height=Always(),
                    style="class:input.rule",
                ),
            ],
            style="class:input.body",
        )

    @property
    def text(self) -> str:
        return self.buffer.text

    def reset(self) -> None:
        self.buffer.reset()

    def newline(self) -> None:
        self.buffer.insert_text("\n")
