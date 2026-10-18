"""Small time formatting helpers for the terminal UI."""

from __future__ import annotations


def format_duration(seconds: float) -> str:
    """Human-ish duration: ``3s``, ``2m 3s``, ``1h 2m``."""
    total = max(0, int(round(seconds)))
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s" if secs else f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m" if minutes else f"{hours}h"


def format_elapsed(seconds: float) -> str:
    """Short elapsed time: ``0.4s``, ``3.2s``, ``12s``, ``2m 3s``."""
    if seconds < 10:
        return f"{max(0.0, seconds):.1f}s"
    return format_duration(seconds)
