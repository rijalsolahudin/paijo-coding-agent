"""`write` tool: create or overwrite a UTF-8 file."""

from __future__ import annotations

import codecs
import difflib

from tools.utils import (
    MUTATION_LOCK,
    ToolOutput,
    atomic_write,
    decode,
    encode,
    ensure_size,
    read_bytes,
    relative,
    resolve_path,
    to_lf,
)


def write(path: str, content: str) -> ToolOutput:
    """Create or overwrite a UTF-8 file, creating parent directories as needed.

    Args:
        path: File to write, relative to the workspace root.
        content: Full file content to store.
    """
    target = resolve_path(path)
    data = encode(content, bom=False)
    ensure_size(data, what="content")

    existed = target.exists()
    old_text = ""
    with MUTATION_LOCK:
        # Keep a BOM if the file we are overwriting already had one.
        if existed:
            try:
                raw = read_bytes(target)
                old_text, _ = decode(raw)
                if raw.startswith(codecs.BOM_UTF8):
                    data = encode(content, bom=True)
            except Exception:
                old_text = ""
        atomic_write(target, data)

    diff = "\n".join(
        difflib.unified_diff(
            to_lf(old_text).splitlines(),
            to_lf(content).splitlines(),
            fromfile=relative(target),
            tofile=relative(target),
            lineterm="",
            n=3,
        )
    )

    verb = "Overwrote" if existed else "Wrote"
    return ToolOutput(f"{verb} {relative(target)} ({len(data)} bytes)", diff)
