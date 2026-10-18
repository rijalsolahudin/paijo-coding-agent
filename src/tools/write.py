"""`write` tool: create or overwrite a UTF-8 file."""

from __future__ import annotations

import codecs

from tools.utils import (
    MUTATION_LOCK,
    atomic_write,
    encode,
    ensure_size,
    read_bytes,
    relative,
    resolve_path,
)


def write(path: str, content: str) -> str:
    """Create or overwrite a UTF-8 file, creating parent directories as needed.

    Args:
        path: File to write, relative to the workspace root.
        content: Full file content to store.
    """
    target = resolve_path(path)
    data = encode(content, bom=False)
    ensure_size(data, what="content")

    existed = target.exists()
    with MUTATION_LOCK:
        # Keep a BOM if the file we are overwriting already had one.
        if existed:
            try:
                if read_bytes(target).startswith(codecs.BOM_UTF8):
                    data = encode(content, bom=True)
            except Exception:
                pass
        atomic_write(target, data)

    verb = "Overwrote" if existed else "Wrote"
    return f"{verb} {relative(target)} ({len(data)} bytes)"
