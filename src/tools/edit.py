"""`edit` tool: replace one unique occurrence of a snippet, returning a diff.

Matching follows the same idea as Pi's edit tool: try an exact match first, then
fall back to a normalised match (NFKC, trimmed trailing whitespace, smart quotes,
Unicode dashes and exotic spaces) that keeps leading indentation intact. Only the
touched lines are rewritten, so the rest of the file survives byte-for-byte,
including its BOM and newline style.
"""

from __future__ import annotations

import difflib
import unicodedata

from tools.utils import (
    MUTATION_LOCK,
    ToolError,
    atomic_write,
    decode,
    encode,
    ensure_size,
    newline_of,
    read_bytes,
    relative,
    resolve_path,
    stamp,
    to_lf,
    truncate,
)

# Characters that look like ASCII punctuation but are not.
_EQUIVALENTS = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2212": "-",
        "\u00a0": " ",
        "\u2007": " ",
        "\u2009": " ",
        "\u202f": " ",
    }
)


def _normalized(line: str) -> str:
    """Fold a line for comparison: keep leading indent, drop trailing space."""
    folded = unicodedata.normalize("NFKC", line).translate(_EQUIVALENTS)
    return folded.rstrip()


def _locate(lines: list[str], target: list[str]) -> list[int]:
    """Line indices where ``target`` (already normalised) matches."""
    span = len(target)
    hits = []
    for start in range(len(lines) - span + 1):
        window = [_normalized(line) for line in lines[start : start + span]]
        if window == target:
            hits.append(start)
    return hits


def _trim_trailing_blanks(lines: list[str]) -> list[str]:
    trimmed = list(lines)
    while trimmed and not trimmed[-1].strip():
        trimmed.pop()
    return trimmed


def _apply(source: str, old_text: str, new_text: str) -> str:
    """Return ``source`` with one occurrence of ``old_text`` replaced."""
    old = to_lf(old_text)
    new = to_lf(new_text)

    exact = source.count(old)
    if exact == 1:
        return source.replace(old, new)
    if exact > 1:
        raise ToolError(
            f"old_text matches {exact} places in the file; include more surrounding context"
        )

    lines = source.split("\n")
    target = _trim_trailing_blanks(old.split("\n"))
    if not target:
        raise ToolError("old_text must contain something other than whitespace")

    hits = _locate(lines, [_normalized(line) for line in target])
    if not hits:
        raise ToolError("old_text was not found in the file (exact and normalised match failed)")
    if len(hits) > 1:
        raise ToolError(
            f"old_text matches {len(hits)} places after normalising; "
            "include more surrounding context"
        )

    start = hits[0]
    end = start + len(target)
    replacement = _trim_trailing_blanks(new.split("\n"))
    return "\n".join([*lines[:start], *replacement, *lines[end:]])


def edit(path: str, old_text: str, new_text: str) -> str:
    """Replace one unique occurrence of old_text with new_text.

    Returns a unified diff of the change. Fails when the search text is empty,
    missing, ambiguous, or when the replacement changes nothing.

    Args:
        path: File to edit, relative to the workspace root.
        old_text: Snippet to find; must appear exactly once.
        new_text: Replacement snippet.
    """
    if not old_text.strip():
        raise ToolError("old_text must contain something other than whitespace")

    target = resolve_path(path)

    with MUTATION_LOCK:
        before_stamp = stamp(target)
        if before_stamp is None:
            raise ToolError(f"{relative(target)} does not exist")

        data = read_bytes(target)
        ensure_size(data, what=relative(target))
        text, bom = decode(data)
        newline = newline_of(text)
        source = to_lf(text)

        updated = _apply(source, old_text, new_text)
        if updated == source:
            raise ToolError("replacement produced no change")

        if stamp(target) != before_stamp:
            raise ToolError("file changed while editing; read it again and retry")

        result = updated.replace("\n", newline) if newline == "\r\n" else updated
        atomic_write(target, encode(result, bom=bom))

    diff = difflib.unified_diff(
        source.split("\n"),
        updated.split("\n"),
        fromfile=relative(target),
        tofile=relative(target),
        lineterm="",
        n=3,
    )
    return truncate("\n".join(diff))
