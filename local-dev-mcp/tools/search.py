"""Search tools: find files by name/glob and search file contents by regex.

Uses ripgrep (``rg``) when available for speed, and otherwise falls back to a
pure-Python implementation so the tools always work.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
from pathlib import Path
from typing import Optional

from config import CONFIG
from utils.helpers import require_tool, run_command, which

DEFAULT_IGNORE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".idea", ".vscode", "dist", "build", "target",
}


def find_files(pattern: str, path: str = ".", max_results: int = 500,
               include_hidden: bool = False) -> dict:
    """Find files whose name matches a glob ``pattern`` (e.g. ``*.py``)."""
    root = CONFIG.check_path(path)
    if not root.exists():
        return {"error": f"No such path: {root}"}
    matches: list[str] = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in DEFAULT_IGNORE_DIRS and (include_hidden or not d.startswith("."))
        ]
        for filename in filenames:
            if not include_hidden and filename.startswith("."):
                continue
            if fnmatch.fnmatch(filename, pattern):
                matches.append(str(Path(dirpath) / filename))
                if len(matches) >= max_results:
                    truncated = True
                    break
        if truncated:
            break
    return {"pattern": pattern, "root": str(root), "count": len(matches),
            "truncated": truncated, "files": matches}


def _search_text_rg(query: str, root: Path, glob: Optional[str],
                    ignore_case: bool, max_results: int, is_regex: bool) -> dict:
    args = ["rg", "--json", "--max-count", "50"]
    if ignore_case:
        args.append("--ignore-case")
    if not is_regex:
        args.append("--fixed-strings")
    if glob:
        args += ["--glob", glob]
    args += ["--", query, str(root)]
    result = run_command(args, timeout=CONFIG.command_timeout,
                         max_output_bytes=CONFIG.max_output_bytes)
    hits: list[dict] = []
    for line in result["stdout"].splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "match":
            continue
        data = event["data"]
        hits.append({
            "file": data["path"].get("text"),
            "line_number": data["line_number"],
            "line": (data["lines"].get("text") or "").rstrip("\n"),
        })
        if len(hits) >= max_results:
            break
    return {"query": query, "root": str(root), "engine": "ripgrep",
            "count": len(hits), "matches": hits}


def _search_text_python(query: str, root: Path, glob: Optional[str],
                        ignore_case: bool, max_results: int, is_regex: bool) -> dict:
    flags = re.IGNORECASE if ignore_case else 0
    pattern = re.compile(query if is_regex else re.escape(query), flags)
    hits: list[dict] = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORE_DIRS and not d.startswith(".")]
        for filename in filenames:
            if glob and not fnmatch.fnmatch(filename, glob):
                continue
            file_path = Path(dirpath) / filename
            try:
                with file_path.open("r", encoding="utf-8", errors="strict") as fh:
                    for lineno, line in enumerate(fh, start=1):
                        if pattern.search(line):
                            hits.append({"file": str(file_path), "line_number": lineno,
                                         "line": line.rstrip("\n")[:500]})
                            if len(hits) >= max_results:
                                truncated = True
                                break
            except (UnicodeDecodeError, OSError):
                continue  # skip binary / unreadable files
            if truncated:
                break
        if truncated:
            break
    return {"query": query, "root": str(root), "engine": "python",
            "count": len(hits), "truncated": truncated, "matches": hits}


def search_text(query: str, path: str = ".", glob: Optional[str] = None,
                ignore_case: bool = False, max_results: int = 200,
                is_regex: bool = True) -> dict:
    """Search file contents for ``query`` (regex by default)."""
    root = CONFIG.check_path(path)
    if not root.exists():
        return {"error": f"No such path: {root}"}
    if which("rg"):
        return _search_text_rg(query, root, glob, ignore_case, max_results, is_regex)
    return _search_text_python(query, root, glob, ignore_case, max_results, is_regex)


def register(mcp) -> None:
    @mcp.tool()
    def search_find_files(pattern: str, path: str = ".", max_results: int = 500,
                          include_hidden: bool = False) -> dict:
        """Find files by name glob (e.g. '*.py', 'Dockerfile') under a directory."""
        return find_files(pattern, path, max_results, include_hidden)

    @mcp.tool()
    def search_in_files(query: str, path: str = ".", glob: Optional[str] = None,
                        ignore_case: bool = False, max_results: int = 200,
                        is_regex: bool = True) -> dict:
        """Search file contents for text/regex (uses ripgrep if installed)."""
        return search_text(query, path, glob, ignore_case, max_results, is_regex)
