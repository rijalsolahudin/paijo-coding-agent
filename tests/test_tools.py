"""The four tools: file access, matching, limits and process control."""

from __future__ import annotations

import codecs
import os

import pytest

from tools import ToolError, bash, dispatch, edit, read, write


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


# -- read -------------------------------------------------------------------


def test_read_returns_numbered_lines(workspace):
    (workspace / "a.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")

    out = read("a.txt", offset=2, limit=1)

    assert "     2\ttwo" in out
    assert "one" not in out


def test_read_caps_at_2000_lines(workspace):
    (workspace / "big.txt").write_text("\n".join("a" for _ in range(2100)), encoding="utf-8")

    out = read("big.txt", limit=5000)

    assert "  2000\ta" in out
    assert "  2001\ta" not in out
    assert "showing lines 1-2000 of 2100" in out


def test_read_rejects_files_over_two_megabytes(workspace):
    (workspace / "huge.txt").write_bytes(b"x" * (2 * 1024 * 1024 + 1))

    with pytest.raises(ToolError, match="MB limit"):
        read("huge.txt")


def test_read_rejects_missing_files(workspace):
    with pytest.raises(ToolError, match="does not exist"):
        read("nope.txt")


# -- workspace limits -------------------------------------------------------


def test_paths_outside_the_workspace_are_rejected(workspace):
    (workspace.parent / "outside.txt").write_text("secret", encoding="utf-8")

    with pytest.raises(ToolError, match="outside the workspace"):
        read("../outside.txt")
    with pytest.raises(ToolError, match="outside the workspace"):
        write("../outside.txt", "overwritten")


def test_symlinks_escaping_the_workspace_are_rejected(workspace):
    outside = workspace.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    (workspace / "link.txt").symlink_to(outside)

    with pytest.raises(ToolError, match="outside the workspace"):
        read("link.txt")


# -- write ------------------------------------------------------------------


def test_write_creates_parent_directories(workspace):
    result = write("a/b/c.txt", "hello")

    assert (workspace / "a/b/c.txt").read_text(encoding="utf-8") == "hello"
    assert "Wrote a/b/c.txt" in result


def test_write_keeps_an_existing_bom(workspace):
    (workspace / "b.txt").write_bytes(codecs.BOM_UTF8 + b"old")

    write("b.txt", "new")

    assert (workspace / "b.txt").read_bytes() == codecs.BOM_UTF8 + b"new"


# -- edit -------------------------------------------------------------------


def test_edit_replaces_once_and_returns_a_diff(workspace):
    (workspace / "f.txt").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    diff = edit("f.txt", "beta", "BETA")

    assert "-beta" in diff and "+BETA" in diff
    assert (workspace / "f.txt").read_text(encoding="utf-8") == "alpha\nBETA\ngamma\n"


def test_edit_rejects_blank_search_text(workspace):
    (workspace / "f.txt").write_text("x", encoding="utf-8")

    with pytest.raises(ToolError, match="whitespace"):
        edit("f.txt", "   ", "y")


def test_edit_rejects_ambiguous_matches(workspace):
    (workspace / "f.txt").write_text("x = 1\ny = 2\nx = 1\n", encoding="utf-8")

    with pytest.raises(ToolError, match="matches 2 places"):
        edit("f.txt", "x = 1", "x = 9")


def test_edit_rejects_missing_text(workspace):
    (workspace / "f.txt").write_text("hello\n", encoding="utf-8")

    with pytest.raises(ToolError, match="not found"):
        edit("f.txt", "goodbye", "hi")


def test_edit_rejects_a_replacement_that_changes_nothing(workspace):
    (workspace / "f.txt").write_text("hello\n", encoding="utf-8")

    with pytest.raises(ToolError, match="no change"):
        edit("f.txt", "hello", "hello")


def test_edit_fuzzy_matches_smart_punctuation_and_trailing_space(workspace):
    (workspace / "f.txt").write_text('a = "x"\u2014y  \nb = 2\n', encoding="utf-8")

    edit("f.txt", 'a = "x"-y', 'a = "z"')

    assert (workspace / "f.txt").read_text(encoding="utf-8") == 'a = "z"\nb = 2\n'


def test_edit_leaves_untouched_lines_byte_identical(workspace):
    original = "keep   \ntarget\nkeep2\t\n"
    (workspace / "f.txt").write_text(original, encoding="utf-8")

    edit("f.txt", "target", "done")

    assert (workspace / "f.txt").read_text(encoding="utf-8") == "keep   \ndone\nkeep2\t\n"


def test_edit_preserves_crlf_and_bom(workspace):
    (workspace / "f.txt").write_bytes(codecs.BOM_UTF8 + b"one\r\ntwo\r\n")

    edit("f.txt", "two", "TWO")

    data = (workspace / "f.txt").read_bytes()
    assert data.startswith(codecs.BOM_UTF8)
    assert b"one\r\nTWO\r\n" in data


def test_edit_preserves_permission_bits(workspace):
    script = workspace / "run.sh"
    script.write_text("echo x\n", encoding="utf-8")
    script.chmod(0o751)

    edit("run.sh", "echo x", "echo y")

    assert (script.stat().st_mode & 0o777) == 0o751


# -- bash -------------------------------------------------------------------


def test_bash_returns_output_and_exit_code(workspace):
    out = bash("echo hello; exit 3")

    assert "hello" in out
    assert "exit code: 3" in out


def test_bash_runs_in_the_workspace(workspace):
    (workspace / "here.txt").write_text("x", encoding="utf-8")

    assert "here.txt" in bash("ls")


def test_bash_timeout_kills_the_process_group(workspace):
    out = bash("sleep 5", timeout=1)

    assert "timed out after 1s" in out


def test_bash_validates_the_timeout(workspace):
    with pytest.raises(ToolError, match="timeout"):
        bash("echo hi", timeout=0)
    with pytest.raises(ToolError, match="timeout"):
        bash("echo hi", timeout=301)


# -- dispatch ---------------------------------------------------------------


def test_dispatch_unknown_tool_raises():
    with pytest.raises(ToolError, match="unknown tool"):
        dispatch("nope", {})


def test_dispatch_runs_a_tool(workspace):
    (workspace / "d.txt").write_text("hi\n", encoding="utf-8")

    assert "hi" in dispatch("read", {"path": "d.txt"})
