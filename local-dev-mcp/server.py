"""local-dev-mcp — a local MCP server that turns Notion AI (or any MCP client)
into a Claude Code-style local development agent.

Run it with::

    python server.py                # stdio transport (default, for MCP clients)
    python server.py --transport sse --host 127.0.0.1 --port 8000

The server registers every tool module in :mod:`tools` and then hands control
to the MCP runtime.
"""

from __future__ import annotations

import argparse
import sys

from mcp.server.fastmcp import FastMCP

from config import CONFIG, DEFAULT_ROOTS_FILE
from tools import ALL_MODULES, register_all
from utils.logger import get_logger

log = get_logger("server")

INSTRUCTIONS = """\
This server exposes local development capabilities to the connected AI agent:
filesystem access, a real terminal (including background/interactive sessions),
git, project analysis, process/system inspection, HTTP + web fetch, databases,
Docker/Kubernetes, archives, editor integration and (where a display exists)
GUI automation.

Prefer the specific tools (e.g. git_status, fs_read_file) over raw terminal_run
when one exists, and consult workspace_detect_project first when exploring an
unfamiliar repository.
"""


def _build_transport_security():
    """DNS-rebinding protection settings for the network transports.

    Behind a tunnel the Host header is the public domain, which FastMCP's default
    (localhost-only) allow-list would reject with HTTP 421. Since the auth token
    is the real gate, host validation is disabled unless the operator pins hosts
    via LOCAL_DEV_MCP_ALLOWED_HOSTS.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    if CONFIG.allowed_hosts:
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=CONFIG.allowed_hosts + ["127.0.0.1:*", "localhost:*", "[::1]:*"],
            allowed_origins=CONFIG.allowed_hosts,
        )
    return TransportSecuritySettings(enable_dns_rebinding_protection=False)


def build_server() -> FastMCP:
    mcp = FastMCP(
        "local-dev-mcp",
        instructions=INSTRUCTIONS,
        transport_security=_build_transport_security(),
    )
    register_all(mcp)
    return mcp


def _log_startup() -> None:
    log.info("Starting local-dev-mcp")
    log.info("Workspace roots: %s",
             ", ".join(str(r) for r in CONFIG.workspace_roots) or "(unrestricted)")
    log.info("Allow-list file: %s (%s)", DEFAULT_ROOTS_FILE,
             "found" if DEFAULT_ROOTS_FILE.exists() else "not present")
    log.info(
        "Capabilities: write=%s delete=%s terminal=%s network=%s gui=%s database=%s",
        CONFIG.allow_write, CONFIG.allow_delete, CONFIG.allow_terminal,
        CONFIG.allow_network, CONFIG.allow_gui, CONFIG.allow_database,
    )
    log.info("Loaded %d tool modules", len(ALL_MODULES))
    if CONFIG.allowed_hosts:
        log.info("Host validation ENABLED for: %s", ", ".join(CONFIG.allowed_hosts))
    else:
        log.info("Host validation disabled (works behind tunnels; token is the gate).")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="local-dev-mcp server")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"],
                        default="stdio", help="Transport to serve on (default: stdio).")
    parser.add_argument("--host", default="127.0.0.1", help="Host for network transports.")
    parser.add_argument("--port", type=int, default=8000, help="Port for network transports.")
    args = parser.parse_args(argv)

    _log_startup()
    mcp = build_server()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
        return

    # Network transports: build the ASGI app so we can enforce token auth,
    # then serve it with uvicorn.
    import uvicorn

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    app = mcp.sse_app() if args.transport == "sse" else mcp.streamable_http_app()

    if CONFIG.auth_token:
        from utils.auth import wrap_with_auth

        app = wrap_with_auth(app, CONFIG.auth_token)
        log.info("Token authentication is ENABLED for the %s endpoint.", args.transport)
    else:
        log.warning(
            "No LOCAL_DEV_MCP_AUTH_TOKEN set: the %s endpoint is UNAUTHENTICATED. "
            "Anyone who can reach it can control this machine. Set a token before "
            "exposing it over a tunnel.",
            args.transport,
        )

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Shutting down (keyboard interrupt).")
        sys.exit(0)
