"""Git tools.

A generic ``git_run`` passthrough covers every subcommand, and a set of
convenience wrappers make the common operations (status, diff, commit, log,
branch, checkout, merge, rebase, stash, pull, push, blame) first-class.
"""

from __future__ import annotations

from typing import Optional

from config import CONFIG
from utils.helpers import require_tool, run_command


def _git(args: list[str], cwd: Optional[str], timeout: Optional[int] = None) -> dict:
    missing = require_tool("git")
    if missing:
        return missing
    workdir = CONFIG.check_path(cwd) if cwd else CONFIG.default_cwd
    return run_command(
        ["git", *args],
        cwd=workdir,
        timeout=timeout or CONFIG.command_timeout,
        max_output_bytes=CONFIG.max_output_bytes,
    )


def register(mcp) -> None:
    @mcp.tool()
    def git_run(args: list[str], cwd: Optional[str] = None) -> dict:
        """Run an arbitrary git command, e.g. args=['rebase','-i','HEAD~3']."""
        return _git(args, cwd)

    @mcp.tool()
    def git_status(cwd: Optional[str] = None) -> dict:
        """Show working tree status (porcelain + branch info)."""
        return _git(["status", "--branch", "--porcelain=v1"], cwd)

    @mcp.tool()
    def git_diff(cwd: Optional[str] = None, staged: bool = False,
                 path: Optional[str] = None) -> dict:
        """Show a diff of unstaged (or staged) changes, optionally for one path."""
        args = ["diff"]
        if staged:
            args.append("--staged")
        if path:
            args += ["--", path]
        return _git(args, cwd)

    @mcp.tool()
    def git_add(paths: list[str], cwd: Optional[str] = None) -> dict:
        """Stage one or more paths (use ['.'] for everything)."""
        return _git(["add", *paths], cwd)

    @mcp.tool()
    def git_commit(message: str, cwd: Optional[str] = None, amend: bool = False,
                   all_tracked: bool = False) -> dict:
        """Create a commit. Set amend=true to amend the last commit."""
        args = ["commit", "-m", message]
        if amend:
            args.append("--amend")
        if all_tracked:
            args.append("-a")
        return _git(args, cwd)

    @mcp.tool()
    def git_log(cwd: Optional[str] = None, max_count: int = 20,
                oneline: bool = True, path: Optional[str] = None) -> dict:
        """Show commit history."""
        args = ["log", f"-n{max_count}"]
        if oneline:
            args += ["--pretty=format:%h %an %ad %s", "--date=short"]
        if path:
            args += ["--", path]
        return _git(args, cwd)

    @mcp.tool()
    def git_branch(cwd: Optional[str] = None, create: Optional[str] = None,
                   delete: Optional[str] = None, list_all: bool = True) -> dict:
        """List, create, or delete branches."""
        if create:
            return _git(["branch", create], cwd)
        if delete:
            return _git(["branch", "-D", delete], cwd)
        args = ["branch"]
        if list_all:
            args.append("-a")
        return _git(args, cwd)

    @mcp.tool()
    def git_checkout(target: str, cwd: Optional[str] = None, create: bool = False) -> dict:
        """Checkout a branch/commit/path. Set create=true to make a new branch."""
        args = ["checkout"]
        if create:
            args.append("-b")
        args.append(target)
        return _git(args, cwd)

    @mcp.tool()
    def git_merge(branch: str, cwd: Optional[str] = None, no_ff: bool = False) -> dict:
        """Merge a branch into the current branch."""
        args = ["merge"]
        if no_ff:
            args.append("--no-ff")
        args.append(branch)
        return _git(args, cwd)

    @mcp.tool()
    def git_rebase(onto: str, cwd: Optional[str] = None) -> dict:
        """Rebase the current branch onto another ref."""
        return _git(["rebase", onto], cwd)

    @mcp.tool()
    def git_cherry_pick(commit: str, cwd: Optional[str] = None) -> dict:
        """Cherry-pick a commit onto the current branch."""
        return _git(["cherry-pick", commit], cwd)

    @mcp.tool()
    def git_stash(cwd: Optional[str] = None, action: str = "push",
                  message: Optional[str] = None) -> dict:
        """Manage the stash. action = push | pop | list | drop | apply."""
        args = ["stash", action]
        if action == "push" and message:
            args += ["-m", message]
        return _git(args, cwd)

    @mcp.tool()
    def git_blame(path: str, cwd: Optional[str] = None,
                  start_line: Optional[int] = None, end_line: Optional[int] = None) -> dict:
        """Show line-by-line authorship for a file."""
        args = ["blame"]
        if start_line and end_line:
            args += ["-L", f"{start_line},{end_line}"]
        args += ["--", path]
        return _git(args, cwd)

    @mcp.tool()
    def git_pull(cwd: Optional[str] = None, remote: str = "origin",
                 branch: Optional[str] = None) -> dict:
        """Pull from a remote."""
        args = ["pull", remote]
        if branch:
            args.append(branch)
        return _git(args, cwd)

    @mcp.tool()
    def git_push(cwd: Optional[str] = None, remote: str = "origin",
                 branch: Optional[str] = None, set_upstream: bool = False,
                 force: bool = False) -> dict:
        """Push to a remote. set_upstream adds -u; force adds --force-with-lease."""
        args = ["push"]
        if set_upstream:
            args.append("-u")
        if force:
            args.append("--force-with-lease")
        args.append(remote)
        if branch:
            args.append(branch)
        return _git(args, cwd)

    @mcp.tool()
    def git_tag(cwd: Optional[str] = None, name: Optional[str] = None,
                message: Optional[str] = None) -> dict:
        """List tags, or create an annotated tag when name is provided."""
        if name:
            args = ["tag", "-a", name, "-m", message or name]
        else:
            args = ["tag"]
        return _git(args, cwd)
