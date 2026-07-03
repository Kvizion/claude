"""IDE / editor integration.

Interacts with installed editors through their command-line launchers. Detects
common CLIs (VS Code, Cursor, Sublime, JetBrains, vim/nvim) and can open a
project, open a file, or jump to a specific line.
"""

from __future__ import annotations

from typing import Optional

from config import CONFIG
from utils.helpers import run_command, which

# Ordered by preference. Each entry: (cli, human name, supports_goto_line)
EDITORS = [
    ("code", "Visual Studio Code", True),
    ("cursor", "Cursor", True),
    ("code-insiders", "VS Code Insiders", True),
    ("subl", "Sublime Text", True),
    ("idea", "IntelliJ IDEA", True),
    ("pycharm", "PyCharm", True),
    ("clion", "CLion", True),
    ("rider", "Rider", True),
    ("nvim", "Neovim", True),
    ("vim", "Vim", True),
    ("gedit", "gedit", False),
]


def detect_editors() -> dict:
    """List installed editors that this tool knows how to drive."""
    available = [
        {"cli": cli, "name": name, "goto_line": goto, "path": which(cli)}
        for cli, name, goto in EDITORS
        if which(cli)
    ]
    return {"count": len(available), "editors": available,
            "default": available[0]["cli"] if available else None}


def _pick_editor(preferred: Optional[str]) -> Optional[tuple[str, str, bool]]:
    if preferred and which(preferred):
        for cli, name, goto in EDITORS:
            if cli == preferred:
                return cli, name, goto
        return preferred, preferred, True
    for cli, name, goto in EDITORS:
        if which(cli):
            return cli, name, goto
    return None


def open_project(path: str, editor: Optional[str] = None) -> dict:
    """Open a directory as a project in an editor."""
    resolved = CONFIG.check_path(path)
    chosen = _pick_editor(editor)
    if not chosen:
        return {"error": "No supported editor found on PATH.",
                "hint": "Install VS Code ('code'), Sublime ('subl') or a JetBrains launcher."}
    cli, name, _ = chosen
    result = run_command([cli, str(resolved)], timeout=30)
    result["editor"] = name
    return result


def open_file(path: str, line: Optional[int] = None, editor: Optional[str] = None) -> dict:
    """Open a file, optionally jumping to a specific line."""
    resolved = CONFIG.check_path(path)
    chosen = _pick_editor(editor)
    if not chosen:
        return {"error": "No supported editor found on PATH."}
    cli, name, supports_goto = chosen
    if line and supports_goto:
        if cli in ("code", "cursor", "code-insiders"):
            args = [cli, "-g", f"{resolved}:{line}"]
        elif cli == "subl":
            args = [cli, f"{resolved}:{line}"]
        elif cli in ("nvim", "vim"):
            args = [cli, f"+{line}", str(resolved)]
        else:  # JetBrains
            args = [cli, "--line", str(line), str(resolved)]
    else:
        args = [cli, str(resolved)]
    result = run_command(args, timeout=30)
    result["editor"] = name
    return result


def register(mcp) -> None:
    @mcp.tool()
    def ide_detect_editors() -> dict:
        """List installed editors/IDEs that can be driven from the command line."""
        return detect_editors()

    @mcp.tool()
    def ide_open_project(path: str, editor: Optional[str] = None) -> dict:
        """Open a folder as a project in an editor (VS Code, Sublime, JetBrains, ...)."""
        return open_project(path, editor)

    @mcp.tool()
    def ide_open_file(path: str, line: Optional[int] = None, editor: Optional[str] = None) -> dict:
        """Open a file in an editor, optionally jumping to a line number."""
        return open_file(path, line, editor)
