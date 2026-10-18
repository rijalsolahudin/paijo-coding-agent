"""Growing streaming preview, rendered inside the prompt block.

The preview has a bounded height: once it grows past ``max_rows`` the window
stops expanding and scrolls instead, so the newest lines stay visible and the
input is never pushed off-screen. The buffer cursor sits at the end of the text,
which is what makes prompt_toolkit follow the tail. Every rendered line gets a
leading space through the window's line prefix, keeping the plain terminal
background.
"""

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import ConditionalContainer, Window
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.layout.dimension import Dimension

MAX_ROWS = 8


class Preview:
    """Streaming assistant text shown above the input while it arrives."""

    def __init__(self, max_rows: int = MAX_ROWS) -> None:
        self.active = False
        self.buffer = Buffer(multiline=True, read_only=True)
        self.window = Window(
            content=BufferControl(buffer=self.buffer, focusable=False),
            height=Dimension(min=1, max=max_rows),
            wrap_lines=True,
            get_line_prefix=lambda lineno, wrap_count: " ",
        )
        self.container = ConditionalContainer(
            self.window,
            filter=Condition(lambda: self.active),
        )

    @property
    def text(self) -> str:
        return self.buffer.text

    def start(self) -> None:
        self.buffer.set_document(Document(""), bypass_readonly=True)
        self.active = True

    def append(self, piece: str) -> None:
        text = self.buffer.text + piece
        self.buffer.set_document(Document(text), bypass_readonly=True)
        self.buffer.cursor_position = len(text)

    def stop(self) -> None:
        self.active = False
