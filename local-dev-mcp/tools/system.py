"""System introspection tools: OS info, env vars, disk, memory, network."""

from __future__ import annotations

import os
import platform
import shutil
import socket
from typing import Optional

from utils.cache import TTLCache
from utils.helpers import human_size

try:  # optional dependency
    import psutil  # type: ignore

    _HAS_PSUTIL = True
except Exception:  # noqa: BLE001
    _HAS_PSUTIL = False

_cache = TTLCache(default_ttl=3.0)


def system_info() -> dict:
    """Return general information about the host system."""
    def build() -> dict:
        uname = platform.uname()
        info = {
            "system": uname.system,
            "node": uname.node,
            "release": uname.release,
            "version": uname.version,
            "machine": uname.machine,
            "processor": uname.processor,
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "hostname": socket.gethostname(),
        }
        if _HAS_PSUTIL:
            info["boot_time"] = psutil.boot_time()
            info["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        return info

    return _cache.get_or_set("system_info", build)


def env_vars(prefix: Optional[str] = None) -> dict:
    """List environment variables (optionally filtered by prefix).

    Values are returned as-is; do not expose this over an untrusted transport
    if the environment contains secrets.
    """
    items = {k: v for k, v in os.environ.items() if not prefix or k.startswith(prefix)}
    return {"count": len(items), "variables": dict(sorted(items.items()))}


def disk_usage(path: str = "/") -> dict:
    """Show disk usage for the filesystem containing ``path``."""
    try:
        usage = shutil.disk_usage(path)
    except FileNotFoundError:
        return {"error": f"No such path: {path}"}
    return {
        "path": path,
        "total": human_size(usage.total),
        "used": human_size(usage.used),
        "free": human_size(usage.free),
        "percent_used": round(usage.used / usage.total * 100, 1) if usage.total else 0,
    }


def memory_usage() -> dict:
    """Show system memory (and swap) usage."""
    if not _HAS_PSUTIL:
        return {"error": "psutil is not installed; memory stats unavailable.",
                "hint": "pip install psutil"}
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "total": human_size(vm.total),
        "available": human_size(vm.available),
        "used": human_size(vm.used),
        "percent": vm.percent,
        "swap_total": human_size(swap.total),
        "swap_used": human_size(swap.used),
    }


def network_interfaces() -> dict:
    """List network interfaces and their addresses."""
    if _HAS_PSUTIL:
        result = {}
        for name, addrs in psutil.net_if_addrs().items():
            result[name] = [
                {"family": str(a.family), "address": a.address, "netmask": a.netmask}
                for a in addrs
            ]
        return {"engine": "psutil", "interfaces": result}
    try:
        hostname = socket.gethostname()
        return {"engine": "socket", "hostname": hostname,
                "ip": socket.gethostbyname(hostname)}
    except OSError as exc:
        return {"error": str(exc)}


def register(mcp) -> None:
    @mcp.tool()
    def system_get_info() -> dict:
        """Get OS, CPU and Python information about the host machine."""
        return system_info()

    @mcp.tool()
    def system_env_vars(prefix: Optional[str] = None) -> dict:
        """List environment variables, optionally filtered by a name prefix."""
        return env_vars(prefix)

    @mcp.tool()
    def system_disk_usage(path: str = "/") -> dict:
        """Report disk usage for the filesystem containing a path."""
        return disk_usage(path)

    @mcp.tool()
    def system_memory_usage() -> dict:
        """Report RAM and swap usage (requires psutil)."""
        return memory_usage()

    @mcp.tool()
    def system_network_interfaces() -> dict:
        """List network interfaces and their addresses."""
        return network_interfaces()
