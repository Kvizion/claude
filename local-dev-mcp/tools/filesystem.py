"""Filesystem tools: read, write, edit, delete, copy, move, list, tree, info.

Every function returns a JSON-serialisable dict and enforces the path policy
defined in :mod:`config`.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import CONFIG
from utils.helpers import human_size, truncate_text

# Directories that are almost never useful to descend into for a tree/listing.
DEFAULT_IGNORE = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "target",
}


def _stat_dict(path: Path) -> dict:
    st = path.stat()
    return {
        "path": str(path),
        "name": path.name,
        "type": "dir" if path.is_dir() else "file" if path.is_file() else "other",
        "size_bytes": st.st_size,
        "size_human": human_size(st.st_size),
        "modified": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
        "mode": oct(st.st_mode & 0o777),
    }


def read_file(path: str, offset: int = 0, limit: Optional[int] = None) -> dict:
    """Read a text file. ``offset``/``limit`` are line numbers (1-based limit)."""
    resolved = CONFIG.check_path(path)
    if not resolved.exists():
        return {"error": f"No such file: {resolved}"}
    if resolved.is_dir():
        return {"error": f"Path is a directory, not a file: {resolved}"}
    raw = resolved.read_bytes()
    truncated_binary = False
    if len(raw) > CONFIG.max_read_bytes:
        raw = raw[: CONFIG.max_read_bytes]
        truncated_binary = True
    try:
        text = raw.decode("utf-8")
        is_binary = False
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
        is_binary = True

    lines = text.splitlines()
    total_lines = len(lines)
    if offset or limit is not None:
        end = offset + limit if limit is not None else None
        lines = lines[offset:end]
    body = "\n".join(lines)
    body, truncated_text = truncate_text(body, CONFIG.max_read_bytes)
    return {
        "path": str(resolved),
        "content": body,
        "total_lines": total_lines,
        "returned_lines": len(lines),
        "offset": offset,
        "is_binary": is_binary,
        "truncated": truncated_binary or truncated_text,
    }


def write_file(path: str, content: str, create_dirs: bool = True) -> dict:
    """Create or fully overwrite a file."""
    resolved = CONFIG.check_path(path, write=True)
    if create_dirs:
        resolved.parent.mkdir(parents=True, exist_ok=True)
    existed = resolved.exists()
    resolved.write_text(content, encoding="utf-8")
    return {
        "path": str(resolved),
        "action": "overwritten" if existed else "created",
        "bytes_written": len(content.encode("utf-8")),
    }


def append_file(path: str, content: str, create_dirs: bool = True) -> dict:
    """Append text to a file, creating it if necessary."""
    resolved = CONFIG.check_path(path, write=True)
    if create_dirs:
        resolved.parent.mkdir(parents=True, exist_ok=True)
    with resolved.open("a", encoding="utf-8") as fh:
        fh.write(content)
    return {"path": str(resolved), "action": "appended", "bytes_written": len(content.encode("utf-8"))}


def edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> dict:
    """Replace an exact ``old_string`` with ``new_string`` inside a file."""
    resolved = CONFIG.check_path(path, write=True)
    if not resolved.exists():
        return {"error": f"No such file: {resolved}"}
    text = resolved.read_text(encoding="utf-8")
    count = text.count(old_string)
    if count == 0:
        return {"error": "old_string not found in file.", "path": str(resolved)}
    if count > 1 and not replace_all:
        return {
            "error": f"old_string is not unique ({count} matches). "
            "Provide more context or set replace_all=true.",
            "matches": count,
            "path": str(resolved),
        }
    new_text = text.replace(old_string, new_string, -1 if replace_all else 1)
    resolved.write_text(new_text, encoding="utf-8")
    return {"path": str(resolved), "action": "edited", "replacements": count if replace_all else 1}


def delete_file(path: str) -> dict:
    """Delete a single file."""
    resolved = CONFIG.check_path(path, write=True)
    if not CONFIG.allow_delete:
        raise PermissionError("Delete operations are disabled (LOCAL_DEV_MCP_ALLOW_DELETE=false).")
    if not resolved.exists():
        return {"error": f"No such file: {resolved}"}
    if resolved.is_dir():
        return {"error": f"Path is a directory; use remove_directory: {resolved}"}
    resolved.unlink()
    return {"path": str(resolved), "action": "deleted"}


def move_path(source: str, destination: str, overwrite: bool = False) -> dict:
    """Move or rename a file/directory."""
    src = CONFIG.check_path(source, write=True)
    dst = CONFIG.check_path(destination, write=True)
    if not src.exists():
        return {"error": f"No such source: {src}"}
    if dst.exists() and not overwrite:
        return {"error": f"Destination exists (set overwrite=true): {dst}"}
    if dst.exists() and overwrite:
        if dst.is_dir():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return {"source": str(src), "destination": str(dst), "action": "moved"}


def copy_path(source: str, destination: str, overwrite: bool = False) -> dict:
    """Copy a file or directory tree."""
    src = CONFIG.check_path(source)
    dst = CONFIG.check_path(destination, write=True)
    if not src.exists():
        return {"error": f"No such source: {src}"}
    if dst.exists() and not overwrite:
        return {"error": f"Destination exists (set overwrite=true): {dst}"}
    if src.is_dir():
        if dst.exists() and overwrite:
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return {"source": str(src), "destination": str(dst), "action": "copied"}


def make_directory(path: str, parents: bool = True) -> dict:
    """Create a directory."""
    resolved = CONFIG.check_path(path, write=True)
    resolved.mkdir(parents=parents, exist_ok=True)
    return {"path": str(resolved), "action": "created"}


def remove_directory(path: str, recursive: bool = False) -> dict:
    """Remove a directory (empty by default, or recursively)."""
    resolved = CONFIG.check_path(path, write=True)
    if not CONFIG.allow_delete:
        raise PermissionError("Delete operations are disabled (LOCAL_DEV_MCP_ALLOW_DELETE=false).")
    if not resolved.exists():
        return {"error": f"No such directory: {resolved}"}
    if not resolved.is_dir():
        return {"error": f"Not a directory: {resolved}"}
    if recursive:
        shutil.rmtree(resolved)
    else:
        try:
            resolved.rmdir()
        except OSError:
            return {"error": "Directory not empty (set recursive=true).", "path": str(resolved)}
    return {"path": str(resolved), "action": "removed", "recursive": recursive}


def list_directory(path: str = ".", show_hidden: bool = False) -> dict:
    """List the immediate children of a directory."""
    resolved = CONFIG.check_path(path)
    if not resolved.exists():
        return {"error": f"No such directory: {resolved}"}
    if not resolved.is_dir():
        return {"error": f"Not a directory: {resolved}"}
    entries = []
    for child in sorted(resolved.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if not show_hidden and child.name.startswith("."):
            continue
        try:
            entries.append(_stat_dict(child))
        except OSError:
            continue
    return {"path": str(resolved), "count": len(entries), "entries": entries}


def get_file_info(path: str) -> dict:
    """Return metadata about a single path."""
    resolved = CONFIG.check_path(path)
    if not resolved.exists():
        return {"error": f"No such path: {resolved}"}
    info = _stat_dict(resolved)
    info["exists"] = True
    info["absolute"] = str(resolved)
    return info


def build_tree(path: str = ".", max_depth: int = 4, show_hidden: bool = False,
               ignore: Optional[list[str]] = None) -> dict:
    """Build an indented directory tree, skipping noisy directories."""
    resolved = CONFIG.check_path(path)
    if not resolved.exists():
        return {"error": f"No such path: {resolved}"}
    ignore_set = set(ignore) if ignore is not None else set(DEFAULT_IGNORE)
    lines: list[str] = [resolved.name or str(resolved)]
    counter = {"n": 0}
    truncated = {"hit": False}

    def walk(directory: Path, prefix: str, depth: int) -> None:
        if depth > max_depth or truncated["hit"]:
            return
        try:
            children = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except (PermissionError, OSError):
            return
        children = [c for c in children if show_hidden or not c.name.startswith(".")]
        for index, child in enumerate(children):
            if counter["n"] >= CONFIG.tree_max_entries:
                truncated["hit"] = True
                lines.append(prefix + "... (truncated)")
                return
            connector = "└── " if index == len(children) - 1 else "├── "
            suffix = "/" if child.is_dir() else ""
            lines.append(f"{prefix}{connector}{child.name}{suffix}")
            counter["n"] += 1
            if child.is_dir() and child.name not in ignore_set:
                extension = "    " if index == len(children) - 1 else "│   "
                walk(child, prefix + extension, depth + 1)

    walk(resolved, "", 1)
    return {
        "path": str(resolved),
        "tree": "\n".join(lines),
        "entries": counter["n"],
        "truncated": truncated["hit"],
    }


def register(mcp) -> None:
    """Register all filesystem tools on the given FastMCP instance."""

    @mcp.tool()
    def fs_read_file(path: str, offset: int = 0, limit: Optional[int] = None) -> dict:
        """Read a text file's contents. Optionally slice by line offset/limit."""
        return read_file(path, offset, limit)

    @mcp.tool()
    def fs_write_file(path: str, content: str, create_dirs: bool = True) -> dict:
        """Create a new file or overwrite an existing one with the given content."""
        return write_file(path, content, create_dirs)

    @mcp.tool()
    def fs_append_file(path: str, content: str, create_dirs: bool = True) -> dict:
        """Append content to the end of a file (creating it if needed)."""
        return append_file(path, content, create_dirs)

    @mcp.tool()
    def fs_edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> dict:
        """Replace an exact string in a file. Fails if old_string is not unique unless replace_all."""
        return edit_file(path, old_string, new_string, replace_all)

    @mcp.tool()
    def fs_delete_file(path: str) -> dict:
        """Delete a single file."""
        return delete_file(path)

    @mcp.tool()
    def fs_move(source: str, destination: str, overwrite: bool = False) -> dict:
        """Move or rename a file or directory."""
        return move_path(source, destination, overwrite)

    @mcp.tool()
    def fs_copy(source: str, destination: str, overwrite: bool = False) -> dict:
        """Copy a file or a directory tree."""
        return copy_path(source, destination, overwrite)

    @mcp.tool()
    def fs_make_directory(path: str, parents: bool = True) -> dict:
        """Create a directory (with parents by default)."""
        return make_directory(path, parents)

    @mcp.tool()
    def fs_remove_directory(path: str, recursive: bool = False) -> dict:
        """Remove a directory. Set recursive=true to delete a non-empty tree."""
        return remove_directory(path, recursive)

    @mcp.tool()
    def fs_list_directory(path: str = ".", show_hidden: bool = False) -> dict:
        """List the immediate contents of a directory with metadata."""
        return list_directory(path, show_hidden)

    @mcp.tool()
    def fs_file_info(path: str) -> dict:
        """Get metadata (size, type, mtime, permissions) for a path."""
        return get_file_info(path)

    @mcp.tool()
    def fs_tree(path: str = ".", max_depth: int = 4, show_hidden: bool = False) -> dict:
        """Render a directory tree, skipping noisy folders like node_modules and .git."""
        return build_tree(path, max_depth, show_hidden)
