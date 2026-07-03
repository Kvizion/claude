"""Workspace analysis: detect project type, dependencies, code stats, TODOs.

These tools give the agent a fast, structured overview of an unfamiliar
repository without having to read every file.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Optional

from config import CONFIG

# Marker file -> (project type, ecosystem)
PROJECT_MARKERS = {
    "package.json": ("Node.js / JavaScript", "npm"),
    "pnpm-lock.yaml": ("Node.js (pnpm)", "pnpm"),
    "yarn.lock": ("Node.js (yarn)", "yarn"),
    "tsconfig.json": ("TypeScript", "npm"),
    "pyproject.toml": ("Python", "pip/poetry"),
    "requirements.txt": ("Python", "pip"),
    "setup.py": ("Python", "pip"),
    "Pipfile": ("Python", "pipenv"),
    "Cargo.toml": ("Rust", "cargo"),
    "go.mod": ("Go", "go modules"),
    "pom.xml": ("Java", "maven"),
    "build.gradle": ("Java/Kotlin", "gradle"),
    "build.gradle.kts": ("Kotlin", "gradle"),
    "CMakeLists.txt": ("C/C++", "cmake"),
    "Makefile": ("C/C++/generic", "make"),
    "Gemfile": ("Ruby", "bundler"),
    "composer.json": ("PHP", "composer"),
    "Dockerfile": ("Containerised", "docker"),
}

LANG_BY_EXT = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript", ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin",
    ".c": "C", ".h": "C/C++ header", ".cpp": "C++", ".cc": "C++", ".hpp": "C++ header",
    ".cs": "C#", ".rb": "Ruby", ".php": "PHP", ".swift": "Swift", ".m": "Objective-C",
    ".sh": "Shell", ".sql": "SQL",
}

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
               "target", ".mypy_cache", ".pytest_cache", ".idea", ".vscode"}


def detect_project_type(path: str = ".") -> dict:
    """Detect project type(s) by looking for well-known marker files."""
    root = CONFIG.check_path(path)
    if not root.is_dir():
        return {"error": f"Not a directory: {root}"}
    found = []
    for marker, (ptype, ecosystem) in PROJECT_MARKERS.items():
        if (root / marker).exists():
            found.append({"marker": marker, "type": ptype, "ecosystem": ecosystem})
    # detect .csproj / .sln anywhere at top level
    for child in root.iterdir():
        if child.suffix in (".csproj", ".sln"):
            found.append({"marker": child.name, "type": "C# / .NET", "ecosystem": "dotnet"})
    return {"path": str(root), "detected": found,
            "is_git_repo": (root / ".git").exists()}


def list_dependencies(path: str = ".") -> dict:
    """Extract declared dependencies from common manifest files."""
    root = CONFIG.check_path(path)
    deps: dict[str, list] = {}

    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            deps["npm"] = sorted(list(data.get("dependencies", {}).keys()) +
                                 list(data.get("devDependencies", {}).keys()))
        except (json.JSONDecodeError, OSError):
            pass

    req = root / "requirements.txt"
    if req.exists():
        try:
            lines = [l.strip() for l in req.read_text(encoding="utf-8").splitlines()]
            deps["pip"] = [l for l in lines if l and not l.startswith("#")]
        except OSError:
            pass

    cargo = root / "Cargo.toml"
    if cargo.exists():
        try:
            text = cargo.read_text(encoding="utf-8")
            section = re.search(r"\[dependencies\](.*?)(\n\[|\Z)", text, re.DOTALL)
            if section:
                names = re.findall(r"^\s*([A-Za-z0-9_\-]+)\s*=", section.group(1), re.MULTILINE)
                deps["cargo"] = names
        except OSError:
            pass

    gomod = root / "go.mod"
    if gomod.exists():
        try:
            text = gomod.read_text(encoding="utf-8")
            deps["go"] = re.findall(r"^\s+([\w\.\-/]+)\s+v", text, re.MULTILINE)
        except OSError:
            pass

    return {"path": str(root), "dependencies": deps}


def code_stats(path: str = ".", max_files: int = 20_000) -> dict:
    """Count files and lines of code per language across a repository."""
    root = CONFIG.check_path(path)
    by_lang: Counter = Counter()
    lines_by_lang: Counter = Counter()
    total_files = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for filename in filenames:
            ext = Path(filename).suffix
            lang = LANG_BY_EXT.get(ext)
            if not lang:
                continue
            total_files += 1
            if total_files > max_files:
                break
            by_lang[lang] += 1
            file_path = Path(dirpath) / filename
            try:
                with file_path.open("r", encoding="utf-8", errors="ignore") as fh:
                    lines_by_lang[lang] += sum(1 for _ in fh)
            except OSError:
                continue
    summary = [
        {"language": lang, "files": by_lang[lang], "lines": lines_by_lang[lang]}
        for lang in sorted(by_lang, key=lambda l: lines_by_lang[l], reverse=True)
    ]
    return {"path": str(root), "total_code_files": total_files, "by_language": summary}


def find_todos(path: str = ".", markers: Optional[list[str]] = None,
               max_results: int = 300) -> dict:
    """Scan source files for TODO/FIXME/HACK/XXX style markers."""
    root = CONFIG.check_path(path)
    markers = markers or ["TODO", "FIXME", "HACK", "XXX", "BUG"]
    pattern = re.compile(r"\b(" + "|".join(re.escape(m) for m in markers) + r")\b")
    hits = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for filename in filenames:
            if Path(filename).suffix not in LANG_BY_EXT:
                continue
            file_path = Path(dirpath) / filename
            try:
                with file_path.open("r", encoding="utf-8", errors="strict") as fh:
                    for lineno, line in enumerate(fh, 1):
                        if pattern.search(line):
                            hits.append({"file": str(file_path), "line": lineno,
                                         "text": line.strip()[:200]})
                            if len(hits) >= max_results:
                                truncated = True
                                break
            except (UnicodeDecodeError, OSError):
                continue
            if truncated:
                break
        if truncated:
            break
    return {"path": str(root), "markers": markers, "count": len(hits),
            "truncated": truncated, "matches": hits}


def register(mcp) -> None:
    @mcp.tool()
    def workspace_detect_project(path: str = ".") -> dict:
        """Detect the project type(s) and ecosystem by inspecting marker files."""
        return detect_project_type(path)

    @mcp.tool()
    def workspace_dependencies(path: str = ".") -> dict:
        """Extract declared dependencies from manifests (package.json, requirements.txt, ...)."""
        return list_dependencies(path)

    @mcp.tool()
    def workspace_code_stats(path: str = ".") -> dict:
        """Summarise files and lines of code per language across a repository."""
        return code_stats(path)

    @mcp.tool()
    def workspace_find_todos(path: str = ".", markers: Optional[list[str]] = None) -> dict:
        """Find TODO/FIXME/HACK/XXX/BUG markers across the source tree."""
        return find_todos(path, markers)
