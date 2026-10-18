"""Full-width, single-line prompt input.

The visible block is exactly three rows: a blank padding row above, the one-line
editor, and a blank padding row below. The padding comes from an invisible
``Frame`` border painted in the same #393939 as the block, so no box outline is
shown while the whole area still reads as a solid grey band.
"""

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Always, Condition
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.layout import VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.processors import AfterInput, ConditionalProcessor
from prompt_toolkit.widgets import Frame

PROMPT_PREFIX = "› "
PLACEHOLDER = "Ask Paijo to do something…"


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
        self.frame = Frame(body, style="class:input", height=Dimension.exact(3))

    @property
    def text(self) -> str:
        return self.buffer.text

    def reset(self) -> None:
        self.buffer.reset()

    def newline(self) -> None:
        self.buffer.insert_text("\n")
