"""Process tools: list, inspect, and terminate OS processes.

Uses ``psutil`` when installed for rich, cross-platform data; otherwise falls
back to the system ``ps`` command (POSIX) so the basics still work.
"""

from __future__ import annotations

import os
import signal
from typing import Optional

from config import CONFIG
from utils.helpers import run_command, which

try:  # optional dependency
    import psutil  # type: ignore

    _HAS_PSUTIL = True
except Exception:  # noqa: BLE001
    _HAS_PSUTIL = False


def list_processes(sort_by: str = "cpu", limit: int = 30,
                   name_contains: Optional[str] = None) -> dict:
    """List running processes sorted by cpu or memory usage."""
    if _HAS_PSUTIL:
        procs = []
        for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
                if name_contains and name_contains.lower() not in (info.get("name") or "").lower():
                    continue
                procs.append({
                    "pid": info["pid"],
                    "name": info.get("name"),
                    "user": info.get("username"),
                    "cpu_percent": round(info.get("cpu_percent") or 0.0, 1),
                    "memory_percent": round(info.get("memory_percent") or 0.0, 1),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        key = "memory_percent" if sort_by == "memory" else "cpu_percent"
        procs.sort(key=lambda p: p[key], reverse=True)
        return {"engine": "psutil", "count": len(procs), "processes": procs[:limit]}

    if which("ps"):
        sort_flag = "-%mem" if sort_by == "memory" else "-%cpu"
        result = run_command(["ps", "-eo", "pid,user,%cpu,%mem,comm", "--sort", sort_flag])
        lines = result["stdout"].splitlines()
        rows = lines[1 : limit + 1] if len(lines) > 1 else []
        if name_contains:
            rows = [r for r in rows if name_contains.lower() in r.lower()]
        return {"engine": "ps", "count": len(rows), "raw": [lines[0]] + rows if lines else rows}

    return {"error": "Neither psutil nor 'ps' is available on this system."}


def process_info(pid: int) -> dict:
    """Return detailed info about a single process by PID."""
    if _HAS_PSUTIL:
        try:
            proc = psutil.Process(pid)
            with proc.oneshot():
                return {
                    "pid": pid,
                    "name": proc.name(),
                    "status": proc.status(),
                    "user": proc.username(),
                    "cpu_percent": proc.cpu_percent(interval=0.1),
                    "memory_mb": round(proc.memory_info().rss / (1024 * 1024), 1),
                    "cmdline": proc.cmdline(),
                    "cwd": _safe(proc.cwd),
                    "create_time": proc.create_time(),
                }
        except psutil.NoSuchProcess:
            return {"error": f"No process with pid {pid}"}
        except psutil.AccessDenied:
            return {"error": f"Access denied to pid {pid}"}
    return run_command(["ps", "-p", str(pid), "-o", "pid,user,%cpu,%mem,stat,comm,args"])


def kill_process(pid: int, force: bool = False) -> dict:
    """Send SIGTERM (or SIGKILL when force=true) to a process."""
    if not CONFIG.allow_terminal:
        raise PermissionError("Process control is disabled (LOCAL_DEV_MCP_ALLOW_TERMINAL=false).")
    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        os.kill(pid, sig)
        return {"pid": pid, "signal": sig.name, "action": "sent"}
    except ProcessLookupError:
        return {"error": f"No process with pid {pid}"}
    except PermissionError:
        return {"error": f"Permission denied signalling pid {pid}"}


def _safe(fn):
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return None


def register(mcp) -> None:
    @mcp.tool()
    def process_list(sort_by: str = "cpu", limit: int = 30,
                     name_contains: Optional[str] = None) -> dict:
        """List processes sorted by 'cpu' or 'memory', optionally filtered by name."""
        return list_processes(sort_by, limit, name_contains)

    @mcp.tool()
    def process_get(pid: int) -> dict:
        """Get detailed information about a process by PID."""
        return process_info(pid)

    @mcp.tool()
    def process_kill(pid: int, force: bool = False) -> dict:
        """Terminate a process by PID (SIGTERM, or SIGKILL when force=true)."""
        return kill_process(pid, force)
