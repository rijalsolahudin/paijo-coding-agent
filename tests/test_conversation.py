"""Rendering of the static conversation output."""

import io

from rich.console import Console

from conversation import CANCELLED_NOTICE, Conversation
from header import build_header


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


def test_user_message_is_a_right_aligned_dark_bubble():
    console = recording_console()
    conversation = Conversation(console)

    conversation.add_user("hi")

    ansi = console.export_text(styles=True, clear=False)
    assert "\x1b[38;2;221;221;221;48;2;51;51;51m" in ansi  # fg #dddddd on #333333

    line = next(row for row in console.export_text().splitlines() if "hi" in row)
    assert line.index("hi") > console.width - 10  # pushed to the right margin
    assert line.lstrip().startswith("hi ")


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

    out = console.export_text()
    assert "Paijo" in out
    assert "9.9.9" in out
    assert "Enter send" in out
