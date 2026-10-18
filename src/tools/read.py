"""`read` tool: show a UTF-8 file with 1-based line numbers."""

from __future__ import annotations

from tools.utils import (
    ToolError,
    decode,
    ensure_size,
    read_bytes,
    relative,
    resolve_path,
    to_lf,
    truncate,
)

MAX_LINES = 2_000
DEFAULT_LIMIT = 200


def read(path: str, offset: int = 1, limit: int = DEFAULT_LIMIT) -> str:
    """Read a UTF-8 file from the workspace and return it with line numbers.

    Args:
        path: File to read, relative to the workspace root.
        offset: 1-based line number to start from.
        limit: Maximum number of lines to return (capped at 2000).
    """
    if offset < 1:
        raise ToolError("offset must be 1 or greater (it is 1-based)")
    if limit < 1:
        raise ToolError("limit must be 1 or greater")

    target = resolve_path(path)
    data = read_bytes(target)
    ensure_size(data, what=relative(target))

    text, _ = decode(data)
    lines = to_lf(text).split("\n")
    total = len(lines)

    start = min(offset - 1, total)
    wanted = min(limit, MAX_LINES)
    chunk = lines[start : start + wanted]

    body = "\n".join(f"{start + index + 1:>6}\t{line}" for index, line in enumerate(chunk))
    shown_end = start + len(chunk)
    if shown_end < total:
        body += f"\n\n[showing lines {start + 1}-{shown_end} of {total}]"
    return truncate(body)
