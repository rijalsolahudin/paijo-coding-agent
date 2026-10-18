"""Shared helpers for Paijo's file and shell tools.

Every path handed to a tool is resolved against the directory Paijo was launched
from, and anything that escapes it (including via symlinks) is rejected. The
same module also owns the 2 MB size limit, the output truncation marker and the
atomic file replacement used by ``write`` and ``edit``.
"""

from __future__ import annotations

import codecs
import os
import stat
import tempfile
import threading
from pathlib import Path

MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_OUTPUT_CHARS = 20_000

# File mutations are serialised so two tools can never write at the same time.
MUTATION_LOCK = threading.Lock()


class ToolError(Exception):
    """Expected tool failure; the message is returned to the model as output."""


def workspace_root() -> Path:
    """The directory Paijo was started in."""
    return Path.cwd().resolve()


def resolve_path(path: str) -> Path:
    """Resolve ``path`` inside the workspace, rejecting anything outside it."""
    if not path or not path.strip():
        raise ToolError("path must not be empty")
    root = workspace_root()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    # resolve() follows symlinks, so a link pointing outside the workspace is
    # rejected here as well.
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise ToolError(f"path {path!r} is outside the workspace root ({root})")
    return resolved


def relative(path: Path) -> str:
    """A display-friendly path for messages."""
    try:
        return str(path.relative_to(workspace_root()))
    except ValueError:
        return str(path)


def truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    """Cut tool output at ``limit`` characters with a visible marker."""
    if len(text) <= limit:
        return text
    dropped = len(text) - limit
    return text[:limit] + f"\n\n[output truncated: {dropped} more characters not shown]"


def ensure_size(data: bytes, *, what: str) -> None:
    if len(data) > MAX_FILE_BYTES:
        raise ToolError(
            f"{what} is {len(data)} bytes, above the {MAX_FILE_BYTES // (1024 * 1024)} MB limit"
        )


def read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        raise ToolError(f"{relative(path)} does not exist") from None
    except IsADirectoryError:
        raise ToolError(f"{relative(path)} is a directory, not a file") from None
    except PermissionError as exc:
        raise ToolError(f"{relative(path)} is not readable: {exc}") from None


def decode(data: bytes) -> tuple[str, bool]:
    """Decode UTF-8 bytes, reporting whether a BOM was present."""
    bom = data.startswith(codecs.BOM_UTF8)
    if bom:
        data = data[len(codecs.BOM_UTF8) :]
    try:
        return data.decode("utf-8"), bom
    except UnicodeDecodeError as exc:
        raise ToolError(f"file is not valid UTF-8: {exc}") from None


def encode(text: str, *, bom: bool) -> bytes:
    data = text.encode("utf-8")
    return codecs.BOM_UTF8 + data if bom else data


def newline_of(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def to_lf(text: str) -> str:
    return text.replace("\r\n", "\n")


def stamp(path: Path) -> tuple[int, int] | None:
    """Cheap fingerprint used to detect external changes before saving."""
    try:
        info = path.stat()
    except FileNotFoundError:
        return None
    return (info.st_mtime_ns, info.st_size)


def atomic_write(path: Path, data: bytes) -> None:
    """Replace ``path`` atomically, keeping its existing permission bits."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".paijo-", suffix=".tmp")
    tmp_path = Path(tmp)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            os.chmod(tmp_path, stat.S_IMODE(path.stat().st_mode))
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
