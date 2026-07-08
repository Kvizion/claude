"""Tool modules for local-dev-mcp.

Each module exposes a ``register(mcp)`` function that attaches its tools to a
FastMCP server instance. :data:`ALL_MODULES` lists them in load order.
"""

from . import (
    archive,
    browser,
    database,
    docker,
    filesystem,
    git,
    gui,
    ide,
    network,
    process,
    search,
    system,
    terminal,
    workspace,
)

ALL_MODULES = [
    filesystem,
    search,
    terminal,
    git,
    process,
    system,
    network,
    browser,
    database,
    docker,
    workspace,
    ide,
    archive,
    gui,
]


def register_all(mcp) -> None:
    for module in ALL_MODULES:
        module.register(mcp)


__all__ = ["ALL_MODULES", "register_all"]
