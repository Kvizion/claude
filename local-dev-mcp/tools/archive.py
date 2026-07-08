"""Archive tools: create, list and extract zip / tar(.gz/.bz2/.xz) archives.

``.rar`` and ``.7z`` are supported for *extraction* when the ``unrar`` / ``7z``
CLIs are installed; otherwise a clear message is returned. Creating zip/tar is
done with the standard library and always available.
"""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path
from typing import Optional

from config import CONFIG
from utils.helpers import human_size, require_tool, run_command, which

_TAR_MODES = {".tar": "w", ".gz": "w:gz", ".tgz": "w:gz", ".bz2": "w:bz2", ".xz": "w:xz"}


def _is_within(base: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def list_archive(path: str) -> dict:
    """List the entries inside an archive without extracting."""
    archive = CONFIG.check_path(path)
    if not archive.exists():
        return {"error": f"No such file: {archive}"}
    suffix = archive.suffix.lower()
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            entries = [{"name": i.filename, "size": i.file_size} for i in zf.infolist()]
        return {"path": str(archive), "format": "zip", "count": len(entries), "entries": entries}
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tf:
            entries = [{"name": m.name, "size": m.size} for m in tf.getmembers()]
        return {"path": str(archive), "format": "tar", "count": len(entries), "entries": entries}
    return {"error": f"Unsupported or unreadable archive: {suffix}"}


def extract_archive(path: str, destination: str) -> dict:
    """Extract an archive into a destination directory (path traversal safe)."""
    archive = CONFIG.check_path(path)
    dest = CONFIG.check_path(destination, write=True)
    if not archive.exists():
        return {"error": f"No such file: {archive}"}
    dest.mkdir(parents=True, exist_ok=True)

    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                target = dest / member
                if not _is_within(dest, target):
                    return {"error": f"Refusing unsafe path in archive: {member}"}
            zf.extractall(dest)
        return {"path": str(archive), "destination": str(dest), "format": "zip", "action": "extracted"}

    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tf:
            for member in tf.getmembers():
                if not _is_within(dest, dest / member.name):
                    return {"error": f"Refusing unsafe path in archive: {member.name}"}
            tf.extractall(dest)
        return {"path": str(archive), "destination": str(dest), "format": "tar", "action": "extracted"}

    suffix = archive.suffix.lower()
    if suffix == ".rar":
        missing = require_tool("unrar")
        if missing:
            return missing
        return run_command(["unrar", "x", "-o+", str(archive), str(dest)])
    if suffix == ".7z":
        missing = require_tool("7z")
        if missing:
            return missing
        return run_command(["7z", "x", f"-o{dest}", str(archive)])

    return {"error": f"Unsupported archive format: {suffix}"}


def create_archive(destination: str, sources: list[str], format: str = "zip") -> dict:
    """Create a zip or tar archive from a list of files/directories."""
    dest = CONFIG.check_path(destination, write=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    resolved_sources = [CONFIG.check_path(s) for s in sources]
    for src in resolved_sources:
        if not src.exists():
            return {"error": f"No such source: {src}"}

    if format == "zip":
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            for src in resolved_sources:
                if src.is_dir():
                    for file in src.rglob("*"):
                        if file.is_file():
                            zf.write(file, file.relative_to(src.parent))
                else:
                    zf.write(src, src.name)
    elif format in ("tar", "tar.gz", "tgz", "tar.bz2", "tar.xz"):
        mode = {"tar": "w", "tar.gz": "w:gz", "tgz": "w:gz",
                "tar.bz2": "w:bz2", "tar.xz": "w:xz"}[format]
        with tarfile.open(dest, mode) as tf:
            for src in resolved_sources:
                tf.add(src, arcname=src.name)
    else:
        return {"error": f"Unsupported format '{format}'. Use zip/tar/tar.gz/tar.bz2/tar.xz."}

    size = dest.stat().st_size
    return {"destination": str(dest), "format": format, "sources": len(resolved_sources),
            "size": human_size(size)}


def register(mcp) -> None:
    @mcp.tool()
    def archive_list(path: str) -> dict:
        """List the contents of a zip or tar archive."""
        return list_archive(path)

    @mcp.tool()
    def archive_extract(path: str, destination: str) -> dict:
        """Extract a zip/tar archive (and rar/7z when those CLIs are installed)."""
        return extract_archive(path, destination)

    @mcp.tool()
    def archive_create(destination: str, sources: list[str], format: str = "zip") -> dict:
        """Create a zip/tar archive from files or directories."""
        return create_archive(destination, sources, format)
