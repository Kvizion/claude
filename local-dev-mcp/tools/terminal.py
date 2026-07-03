"""Terminal tools.

Two flavours are provided:

* ``terminal_run`` — run a command to completion and get stdout/stderr/exit code.
* ``terminal_session_*`` — start long-running / interactive processes in the
  background, stream their output, send them stdin, and stop them. Multiple
  sessions can run in parallel.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Optional

from config import CONFIG
from utils.helpers import run_command
from utils.logger import get_logger

log = get_logger("terminal")


def _check_terminal_allowed() -> None:
    if not CONFIG.allow_terminal:
        raise PermissionError("Terminal execution is disabled (LOCAL_DEV_MCP_ALLOW_TERMINAL=false).")


def run(command: str, cwd: Optional[str] = None, timeout: Optional[int] = None,
        shell: bool = True, env: Optional[dict] = None) -> dict:
    """Run a command to completion (blocking)."""
    _check_terminal_allowed()
    workdir = CONFIG.check_path(cwd) if cwd else CONFIG.default_cwd
    merged_env = None
    if env:
        merged_env = {**os.environ, **env}
    return run_command(
        command,
        cwd=workdir,
        env=merged_env,
        timeout=timeout or CONFIG.command_timeout,
        shell=shell,
        max_output_bytes=CONFIG.max_output_bytes,
    )


class _Session:
    """A background process whose output is captured by a reader thread."""

    def __init__(self, command: str, cwd: Path, shell: bool, env: Optional[dict]):
        self.id = uuid.uuid4().hex[:12]
        self.command = command
        self.cwd = str(cwd)
        self.created_at = time.time()
        self._buffer: deque[str] = deque(maxlen=10_000)
        self._lock = threading.Lock()
        merged_env = {**os.environ, **env} if env else None
        self.proc = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=merged_env,
            shell=shell,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            with self._lock:
                self._buffer.append(line.rstrip("\n"))

    def read(self, max_lines: int = 200) -> list[str]:
        with self._lock:
            lines = list(self._buffer)
        return lines[-max_lines:]

    def write(self, data: str) -> None:
        if self.proc.stdin and self.proc.poll() is None:
            self.proc.stdin.write(data if data.endswith("\n") else data + "\n")
            self.proc.stdin.flush()

    def stop(self, force: bool = False) -> None:
        if self.proc.poll() is not None:
            return
        try:
            if force:
                self.proc.kill()
            else:
                self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:  # noqa: BLE001 - best effort teardown
            try:
                self.proc.kill()
            except Exception:  # noqa: BLE001
                pass

    def status(self) -> dict:
        rc = self.proc.poll()
        return {
            "session_id": self.id,
            "command": self.command,
            "cwd": self.cwd,
            "running": rc is None,
            "exit_code": rc,
            "pid": self.proc.pid,
            "age_seconds": round(time.time() - self.created_at, 1),
        }


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.Lock()

    def start(self, command: str, cwd: Optional[str], shell: bool, env: Optional[dict]) -> dict:
        workdir = CONFIG.check_path(cwd) if cwd else CONFIG.default_cwd
        session = _Session(command, workdir, shell, env)
        with self._lock:
            self._sessions[session.id] = session
        time.sleep(0.15)  # let fast commands produce some initial output
        status = session.status()
        status["initial_output"] = session.read(50)
        return status

    def list(self) -> dict:
        with self._lock:
            sessions = [s.status() for s in self._sessions.values()]
        return {"count": len(sessions), "sessions": sessions}

    def read(self, session_id: str, max_lines: int = 200) -> dict:
        session = self._get(session_id)
        if session is None:
            return {"error": f"No such session: {session_id}"}
        status = session.status()
        status["output"] = session.read(max_lines)
        return status

    def write(self, session_id: str, data: str) -> dict:
        session = self._get(session_id)
        if session is None:
            return {"error": f"No such session: {session_id}"}
        if session.proc.poll() is not None:
            return {"error": "Session process has already exited.", **session.status()}
        session.write(data)
        time.sleep(0.15)
        status = session.status()
        status["output"] = session.read(50)
        return status

    def stop(self, session_id: str, force: bool = False) -> dict:
        session = self._get(session_id)
        if session is None:
            return {"error": f"No such session: {session_id}"}
        session.stop(force=force)
        with self._lock:
            self._sessions.pop(session_id, None)
        status = session.status()
        status["action"] = "stopped"
        return status

    def _get(self, session_id: str) -> Optional[_Session]:
        with self._lock:
            return self._sessions.get(session_id)


SESSIONS = SessionManager()


def register(mcp) -> None:
    @mcp.tool()
    def terminal_run(command: str, cwd: Optional[str] = None, timeout: Optional[int] = None,
                     shell: bool = True) -> dict:
        """Run a shell command to completion. Returns stdout, stderr and exit code."""
        return run(command, cwd, timeout, shell)

    @mcp.tool()
    def terminal_session_start(command: str, cwd: Optional[str] = None,
                               shell: bool = True) -> dict:
        """Start a long-running or interactive process in the background. Returns a session_id."""
        _check_terminal_allowed()
        return SESSIONS.start(command, cwd, shell, None)

    @mcp.tool()
    def terminal_session_list() -> dict:
        """List all active background terminal sessions."""
        return SESSIONS.list()

    @mcp.tool()
    def terminal_session_read(session_id: str, max_lines: int = 200) -> dict:
        """Read buffered output from a background session."""
        return SESSIONS.read(session_id, max_lines)

    @mcp.tool()
    def terminal_session_write(session_id: str, data: str) -> dict:
        """Send a line of input (stdin) to an interactive background session."""
        _check_terminal_allowed()
        return SESSIONS.write(session_id, data)

    @mcp.tool()
    def terminal_session_stop(session_id: str, force: bool = False) -> dict:
        """Stop a background session (SIGTERM, or SIGKILL when force=true)."""
        return SESSIONS.stop(session_id, force)
