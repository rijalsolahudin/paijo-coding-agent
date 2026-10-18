"""Rendering of the static conversation output."""

import io

from rich.console import Console

from ui.conversation import CANCELLED_NOTICE, MAX_DIFF_LINES, Conversation, format_duration
from ui.header import build_header


def recording_console() -> Console:
    return Console(
        record=True,
        file=io.StringIO(),
        width=80,
        force_terminal=True,
        color_system="truecolor",
        _environ={},
    )


def test_user_message_printed_verbatim_including_multiline():
    console = recording_console()
    conversation = Conversation(console)

    conversation.add_user("baris pertama\nbaris kedua\n\nbaris keempat")

    out = console.export_text()
    assert "baris pertama" in out
    assert "baris kedua" in out
    assert "baris keempat" in out


def test_user_message_is_a_left_aligned_muted_green_block():
    console = recording_console()
    conversation = Conversation(console)

    conversation.add_user("hi")

    ansi = console.export_text(styles=True, clear=False)
    assert "48;2;47;122;60" in ansi  # muted green background (blended, no alpha)
    assert "38;2;255;255;255" in ansi  # white text

    line = next(row for row in console.export_text().splitlines() if "hi" in row)
    assert line.startswith(" ❯ hi")  # one padding cell, then the marker
    assert line.rstrip() == " ❯ hi"


def test_duration_formatting():
    assert format_duration(3.4) == "3s"
    assert format_duration(59.6) == "1m"
    assert format_duration(123) == "2m 3s"
    assert format_duration(120) == "2m"
    assert format_duration(3720) == "1h 2m"


def test_duration_footer_is_printed_below_the_turn():
    console = recording_console()
    conversation = Conversation(console)

    conversation.add_duration(63)

    out = console.export_text()
    assert "Worked for 1m 3s" in out
    assert conversation.durations == [63]


def test_tool_calls_are_printed_as_badges():
    console = recording_console()
    conversation = Conversation(console)

    conversation.add_tool("read", "index.html", True, "     1\tx\n     2\ty\n")
    conversation.add_tool("edit", "index.html", False, "error: not found")

    ansi = console.export_text(styles=True, clear=False)
    out = console.export_text()

    assert "READ" in out
    assert "[index.html]" in out
    assert "2 lines" in out
    assert "error: not found" in out
    assert "48;2;63;185;80" in ansi  # ok: green badge
    assert "48;2;176;58;58" in ansi  # failed: red badge
    assert conversation.tool_calls == [
        ("read", "index.html", True),
        ("edit", "index.html", False),
    ]


def test_tool_badge_shows_elapsed_time():
    console = recording_console()
    conversation = Conversation(console)

    conversation.add_tool("bash", "true", True, "ok", 0.4)

    assert "0.4s" in console.export_text()


def test_diff_is_coloured_like_git():
    console = recording_console()
    conversation = Conversation(console)

    diff = "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-old\n+new\n"
    conversation.add_diff(diff)

    ansi = console.export_text(styles=True, clear=False)
    out = console.export_text()

    assert "Updated a/f.py with 1 addition and 1 removal" in out
    assert "- old" in out
    assert "+ new" in out
    assert "38;2;248;81;73" in ansi  # removed lines: red
    assert "38;2;63;185;80" in ansi  # added lines: green
    assert conversation.diffs == [diff]


def test_long_diffs_are_truncated():
    console = recording_console()
    conversation = Conversation(console)

    diff = "--- a/f.py\n+++ b/f.py\n@@ -1,0 +1,30 @@\n" + "\n".join(
        f"+line {i}" for i in range(MAX_DIFF_LINES + 5)
    )
    conversation.add_diff(diff)

    assert "more lines" in console.export_text()


def test_assistant_reply_is_markdown_with_one_leading_space_per_line():
    console = recording_console()
    conversation = Conversation(console)

    conversation.add_assistant("**tebal**\n\n- satu\n- dua")

    out = console.export_text()
    assert "tebal" in out
    assert "**" not in out  # Markdown syntax is rendered, not printed literally

    rows = [row for row in out.splitlines() if row.strip()]
    assert rows
    assert all(row.startswith(" ") for row in rows)  # leading space on every line


def test_assistant_has_no_name_label():
    console = recording_console()
    conversation = Conversation(console)

    conversation.add_assistant("halo")

    out = console.export_text()
    assert "Joy" not in out
    assert "Paijo" not in out


def test_cancelled_turn_keeps_the_partial_and_shows_a_notice():
    console = recording_console()
    conversation = Conversation(console)

    conversation.add_cancelled("potongan jawaban")

    out = console.export_text()
    assert "potongan jawaban" in out
    assert CANCELLED_NOTICE in out
    assert conversation.notices == [CANCELLED_NOTICE]
    assert conversation.entries == []


def test_failed_turn_shows_a_readable_error():
    console = recording_console()
    conversation = Conversation(console)

    conversation.add_error("", "Saldo/budget habis (429).")

    out = console.export_text()
    assert "Saldo/budget habis" in out
    assert conversation.notices == ["Saldo/budget habis (429)."]
    assert conversation.entries == []


def test_transcript_records_both_roles():
    conversation = Conversation(recording_console())

    conversation.add_user("hai")
    conversation.add_assistant("halo juga")

    assert [entry.role for entry in conversation.entries] == ["user", "assistant"]


def test_header_banner_shows_name_version_and_hotkeys():
    console = recording_console()
    console.print(build_header("9.9.9"))

    ansi = console.export_text(styles=True, clear=False)
    out = console.export_text()
    assert "Paijo" in out
    assert "9.9.9" in out
    assert "Enter send" in out

    # The frame uses the same green as the input rules (#3fb950).
    assert "63;185;80" in ansi
