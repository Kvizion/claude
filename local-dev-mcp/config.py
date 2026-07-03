"""Central configuration for the local-dev-mcp server.

All settings are read from environment variables so the server can be
configured entirely from the MCP client's ``env`` block without editing code.

Security note
-------------
This server exposes very powerful capabilities (arbitrary file access, shell
execution, GUI control, ...). By default it trusts the machine it runs on the
same way Claude Code does, but every dangerous capability can be locked down
through the environment variables documented below.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ENV_PREFIX = "LOCAL_DEV_MCP_"


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(ENV_PREFIX + name, default)


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_paths(name: str) -> list[Path]:
    raw = _env(name)
    if not raw:
        return []
    parts = [p for p in raw.replace(";", os.pathsep).split(os.pathsep) if p.strip()]
    return [Path(p).expanduser().resolve() for p in parts]


@dataclass
class Config:
    """Runtime configuration, normally built with :meth:`from_env`."""

    # If empty, filesystem access is unrestricted. Otherwise every path must
    # live inside one of these roots.
    workspace_roots: list[Path] = field(default_factory=list)

    # Capability switches.
    allow_write: bool = True
    allow_delete: bool = True
    allow_terminal: bool = True
    allow_network: bool = True
    allow_gui: bool = True
    allow_database: bool = True

    # Limits.
    command_timeout: int = 120  # seconds for a single blocking command
    max_output_bytes: int = 200_000  # cap on captured stdout/stderr
    max_read_bytes: int = 2_000_000  # cap on file reads
    tree_max_entries: int = 5_000

    # Default working directory for terminal commands.
    default_cwd: Path = field(default_factory=Path.cwd)

    @classmethod
    def from_env(cls) -> "Config":
        default_cwd = _env("DEFAULT_CWD")
        return cls(
            workspace_roots=_env_paths("ROOTS"),
            allow_write=_env_bool("ALLOW_WRITE", True),
            allow_delete=_env_bool("ALLOW_DELETE", True),
            allow_terminal=_env_bool("ALLOW_TERMINAL", True),
            allow_network=_env_bool("ALLOW_NETWORK", True),
            allow_gui=_env_bool("ALLOW_GUI", True),
            allow_database=_env_bool("ALLOW_DATABASE", True),
            command_timeout=_env_int("COMMAND_TIMEOUT", 120),
            max_output_bytes=_env_int("MAX_OUTPUT_BYTES", 200_000),
            max_read_bytes=_env_int("MAX_READ_BYTES", 2_000_000),
            tree_max_entries=_env_int("TREE_MAX_ENTRIES", 5_000),
            default_cwd=Path(default_cwd).expanduser().resolve()
            if default_cwd
            else Path.cwd(),
        )

    # -- path handling -------------------------------------------------

    def resolve(self, path: str | os.PathLike) -> Path:
        """Expand ``~`` / environment vars and return an absolute path."""
        p = Path(os.path.expandvars(os.path.expanduser(str(path))))
        if not p.is_absolute():
            p = (self.default_cwd / p)
        return p.resolve()

    def is_allowed(self, path: Path) -> bool:
        if not self.workspace_roots:
            return True
        for root in self.workspace_roots:
            try:
                path.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def check_path(self, path: str | os.PathLike, *, write: bool = False) -> Path:
        """Validate a path against the configured policy and return it resolved.

        Raises ``PermissionError`` if the path is outside the allowed roots or
        if a write is attempted while writes are disabled.
        """
        resolved = self.resolve(path)
        if not self.is_allowed(resolved):
            roots = ", ".join(str(r) for r in self.workspace_roots)
            raise PermissionError(
                f"Path '{resolved}' is outside the allowed workspace roots ({roots})."
            )
        if write and not self.allow_write:
            raise PermissionError("Write operations are disabled (LOCAL_DEV_MCP_ALLOW_WRITE=false).")
        return resolved


# A module-level singleton is convenient for the tool modules.
CONFIG = Config.from_env()
