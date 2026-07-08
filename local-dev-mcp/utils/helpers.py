"""Shared helpers: subprocess execution, formatting, safe truncation."""

from __future__ import annotations

import shlex
import subprocess
import time
from pathlib import Path
from typing import Optional, Sequence, Union

from .logger import get_logger

log = get_logger("helpers")

CommandType = Union[str, Sequence[str]]


def human_size(num_bytes: float) -> str:
    """Render a byte count as a human friendly string."""
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(num_bytes) < step:
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{int(num_bytes)} {unit}"
        num_bytes /= step
    return f"{num_bytes:.1f} EB"


def truncate_text(text: str, max_bytes: int) -> tuple[str, bool]:
    """Truncate ``text`` so its UTF-8 encoding is at most ``max_bytes``.

    Returns the (possibly truncated) text and a boolean flag indicating whether
    truncation happened.
    """
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= max_bytes:
        return text, False
    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return truncated, True


def split_command(command: CommandType, shell: bool) -> CommandType:
    """Normalise a command for subprocess.

    When ``shell`` is False and a plain string is given, it is tokenised with
    :func:`shlex.split` so callers can pass a convenient single string.
    """
    if shell:
        return command
    if isinstance(command, str):
        return shlex.split(command, posix=True)
    return list(command)


def run_command(
    command: CommandType,
    *,
    cwd: Optional[Union[str, Path]] = None,
    env: Optional[dict] = None,
    timeout: Optional[float] = None,
    input_text: Optional[str] = None,
    shell: bool = False,
    max_output_bytes: int = 200_000,
) -> dict:
    """Run a command to completion and capture stdout/stderr/exit-code.

    This is the workhorse used by the terminal, git, docker and database
    tools. It never raises for a non-zero exit code; instead the exit code is
    returned in the result so the agent can reason about it.
    """
    args = split_command(command, shell)
    started = time.monotonic()
    timed_out = False
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            env=env,
            input=input_text,
            capture_output=True,
            text=True,
            shell=shell,
            timeout=timeout,
        )
        stdout, stderr, returncode = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        returncode = None
    except FileNotFoundError as exc:
        return {
            "command": command,
            "cwd": str(cwd) if cwd else None,
            "exit_code": 127,
            "stdout": "",
            "stderr": f"Command not found: {exc}",
            "timed_out": False,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }

    stdout, out_truncated = truncate_text(stdout or "", max_output_bytes)
    stderr, err_truncated = truncate_text(stderr or "", max_output_bytes)
    return {
        "command": command if isinstance(command, str) else " ".join(command),
        "cwd": str(cwd) if cwd else None,
        "exit_code": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_truncated": out_truncated,
        "stderr_truncated": err_truncated,
        "timed_out": timed_out,
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


def which(program: str) -> Optional[str]:
    """Thin wrapper over shutil.which kept here for a single import surface."""
    import shutil

    return shutil.which(program)


def require_tool(program: str) -> Optional[dict]:
    """Return an error dict if ``program`` is not on PATH, else ``None``."""
    if which(program) is None:
        return {
            "error": f"'{program}' is not installed or not on PATH.",
            "hint": f"Install '{program}' to use this tool.",
        }
    return None
