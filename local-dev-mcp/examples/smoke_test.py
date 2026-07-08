"""Self-contained smoke test for local-dev-mcp.

Launches the server over stdio (exactly like a real MCP client would), lists the
available tools, and calls a few safe ones. Run it from the project root:

    python examples/smoke_test.py

No Node.js required — it uses the MCP client bundled with the `mcp` package.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _text(result) -> str:
    return result.content[0].text if result.content else ""


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(PROJECT_ROOT / "server.py")],
        cwd=str(PROJECT_ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"Connected to: {init.serverInfo.name}")

            tools = await session.list_tools()
            print(f"Tools available: {len(tools.tools)}\n")

            print("--- system_get_info ---")
            print(_text(await session.call_tool("system_get_info", {}))[:400])

            print("\n--- fs_tree (project root, depth 2) ---")
            print(_text(await session.call_tool(
                "fs_tree", {"path": str(PROJECT_ROOT), "max_depth": 2}))[:600])

            print("\n--- terminal_run: python --version ---")
            print(_text(await session.call_tool(
                "terminal_run", {"command": f'"{sys.executable}" --version'})))

            print("\n--- workspace_detect_project ---")
            print(_text(await session.call_tool(
                "workspace_detect_project", {"path": str(PROJECT_ROOT)})))

    print("\nSmoke test finished OK ✅")


if __name__ == "__main__":
    asyncio.run(main())
