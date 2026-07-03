"""Container tooling: Docker, Docker Compose and Kubernetes (kubectl).

These are thin, safe wrappers over the respective CLIs. If a CLI is not
installed the tool reports that clearly instead of failing hard.
"""

from __future__ import annotations

from typing import Optional

from config import CONFIG
from utils.helpers import require_tool, run_command


def _run(binary: str, args: list[str], cwd: Optional[str] = None) -> dict:
    missing = require_tool(binary)
    if missing:
        return missing
    workdir = CONFIG.check_path(cwd) if cwd else CONFIG.default_cwd
    return run_command([binary, *args], cwd=workdir, timeout=CONFIG.command_timeout,
                       max_output_bytes=CONFIG.max_output_bytes)


def register(mcp) -> None:
    @mcp.tool()
    def docker_ps(all_containers: bool = False) -> dict:
        """List Docker containers (all_containers includes stopped ones)."""
        args = ["ps", "--format", "{{json .}}"]
        if all_containers:
            args.insert(1, "-a")
        return _run("docker", args)

    @mcp.tool()
    def docker_images() -> dict:
        """List local Docker images."""
        return _run("docker", ["images", "--format", "{{json .}}"])

    @mcp.tool()
    def docker_run(args: list[str]) -> dict:
        """Run an arbitrary docker subcommand, e.g. args=['logs','my-container']."""
        return _run("docker", args)

    @mcp.tool()
    def docker_logs(container: str, tail: int = 200) -> dict:
        """Fetch logs from a container."""
        return _run("docker", ["logs", "--tail", str(tail), container])

    @mcp.tool()
    def docker_compose(args: list[str], cwd: Optional[str] = None) -> dict:
        """Run a docker compose command, e.g. args=['up','-d'] in a project dir."""
        return _run("docker", ["compose", *args], cwd=cwd)

    @mcp.tool()
    def kubectl_run(args: list[str]) -> dict:
        """Run a kubectl command, e.g. args=['get','pods','-A']."""
        return _run("kubectl", args)
