"""`bash` tool: run a non-interactive command in the workspace root.

The command runs as *you*, with your permissions. It is **not** sandboxed the way
the file tools are — the workspace path checks in :mod:`tools.utils` do not apply
here, so treat it as code you would type into your own shell.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading

from tools.utils import ToolError, truncate, workspace_root

MIN_TIMEOUT = 1
MAX_TIMEOUT = 300
DEFAULT_TIMEOUT = 30

_lock = threading.Lock()
_active: subprocess.Popen[str] | None = None


def terminate_active() -> None:
    """Kill the process group of the running command, if there is one."""
    with _lock:
        process = _active
    if process is not None and process.poll() is None:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def bash(command: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Run a Bash command in the workspace root and return its output.

    Args:
        command: Command line executed with `bash -c`.
        timeout: Seconds to wait before the process group is killed (1-300).
    """
    global _active

    if not command.strip():
        raise ToolError("command must not be empty")
    if not MIN_TIMEOUT <= timeout <= MAX_TIMEOUT:
        raise ToolError(f"timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT} seconds")

    process = subprocess.Popen(
        command,
        shell=True,
        executable="/bin/bash",
        cwd=str(workspace_root()),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        text=True,
    )

    with _lock:
        _active = process
    try:
        try:
            output, _ = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            terminate_active()
            output, _ = process.communicate()
            return truncate(f"{output}\n[timed out after {timeout}s; process group killed]")
    finally:
        with _lock:
            _active = None

    return truncate(f"{output}\n[exit code: {process.returncode}]")
