"""GUI automation tools: screenshots, mouse, keyboard, clipboard, windows.

These require a graphical session and optional libraries:

* ``pyautogui``  — mouse/keyboard/screenshot
* ``mss``        — fast screenshots (fallback to pyautogui)
* ``pyperclip``  — clipboard

On headless servers these tools return a clear "GUI not available" message
rather than crashing, so the rest of the server keeps working.
"""

from __future__ import annotations

import base64
import io
import platform
import shutil
from pathlib import Path
from typing import Optional

from config import CONFIG


def _check_gui_allowed() -> Optional[dict]:
    if not CONFIG.allow_gui:
        return {"error": "GUI automation is disabled (LOCAL_DEV_MCP_ALLOW_GUI=false)."}
    return None


def _load_pyautogui():
    try:
        import pyautogui  # type: ignore

        pyautogui.FAILSAFE = False
        return pyautogui, None
    except Exception as exc:  # noqa: BLE001 - importing needs a display
        return None, {
            "error": "pyautogui is not available (needs a graphical session).",
            "detail": str(exc),
            "hint": "pip install pyautogui (and run on a machine with a display).",
        }


def screenshot(path: Optional[str] = None, return_base64: bool = False) -> dict:
    """Capture the screen. Saves to a file and/or returns base64 PNG."""
    blocked = _check_gui_allowed()
    if blocked:
        return blocked
    image_bytes: Optional[bytes] = None
    try:
        import mss  # type: ignore
        import mss.tools  # type: ignore

        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[0])
            image_bytes = mss.tools.to_png(shot.rgb, shot.size)
    except Exception:  # noqa: BLE001 - fall back to pyautogui
        pyautogui, err = _load_pyautogui()
        if err:
            return err
        buffer = io.BytesIO()
        pyautogui.screenshot().save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

    result: dict = {"captured": True, "bytes": len(image_bytes)}
    if path:
        dest = CONFIG.check_path(path, write=True)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(image_bytes)
        result["path"] = str(dest)
    if return_base64:
        result["base64_png"] = base64.b64encode(image_bytes).decode("ascii")
    return result


def screen_size() -> dict:
    """Return the primary screen resolution."""
    blocked = _check_gui_allowed()
    if blocked:
        return blocked
    pyautogui, err = _load_pyautogui()
    if err:
        return err
    size = pyautogui.size()
    return {"width": size.width, "height": size.height}


def mouse_move(x: int, y: int, duration: float = 0.0) -> dict:
    """Move the mouse cursor to absolute (x, y)."""
    blocked = _check_gui_allowed()
    if blocked:
        return blocked
    pyautogui, err = _load_pyautogui()
    if err:
        return err
    pyautogui.moveTo(x, y, duration=duration)
    return {"action": "move", "x": x, "y": y}


def mouse_click(x: Optional[int] = None, y: Optional[int] = None, button: str = "left",
                clicks: int = 1) -> dict:
    """Click the mouse (optionally moving to x, y first)."""
    blocked = _check_gui_allowed()
    if blocked:
        return blocked
    pyautogui, err = _load_pyautogui()
    if err:
        return err
    pyautogui.click(x=x, y=y, button=button, clicks=clicks)
    return {"action": "click", "x": x, "y": y, "button": button, "clicks": clicks}


def drag_to(x: int, y: int, button: str = "left", duration: float = 0.2) -> dict:
    """Drag from the current position to (x, y)."""
    blocked = _check_gui_allowed()
    if blocked:
        return blocked
    pyautogui, err = _load_pyautogui()
    if err:
        return err
    pyautogui.dragTo(x, y, button=button, duration=duration)
    return {"action": "drag", "x": x, "y": y, "button": button}


def type_text(text: str, interval: float = 0.0) -> dict:
    """Type a string of text as keyboard input."""
    blocked = _check_gui_allowed()
    if blocked:
        return blocked
    pyautogui, err = _load_pyautogui()
    if err:
        return err
    pyautogui.write(text, interval=interval)
    return {"action": "type", "length": len(text)}


def hotkey(keys: list[str]) -> dict:
    """Press a key combination, e.g. keys=['ctrl','c']."""
    blocked = _check_gui_allowed()
    if blocked:
        return blocked
    pyautogui, err = _load_pyautogui()
    if err:
        return err
    pyautogui.hotkey(*keys)
    return {"action": "hotkey", "keys": keys}


def clipboard_get() -> dict:
    """Read the system clipboard."""
    blocked = _check_gui_allowed()
    if blocked:
        return blocked
    try:
        import pyperclip  # type: ignore

        return {"text": pyperclip.paste()}
    except Exception as exc:  # noqa: BLE001
        return {"error": "pyperclip not available.", "detail": str(exc),
                "hint": "pip install pyperclip"}


def clipboard_set(text: str) -> dict:
    """Write text to the system clipboard."""
    blocked = _check_gui_allowed()
    if blocked:
        return blocked
    try:
        import pyperclip  # type: ignore

        pyperclip.copy(text)
        return {"action": "clipboard_set", "length": len(text)}
    except Exception as exc:  # noqa: BLE001
        return {"error": "pyperclip not available.", "detail": str(exc),
                "hint": "pip install pyperclip"}


def launch_application(command: str) -> dict:
    """Launch a GUI application by command/path (fire and forget)."""
    blocked = _check_gui_allowed()
    if blocked:
        return blocked
    if not CONFIG.allow_terminal:
        return {"error": "Launching applications requires terminal permission."}
    import subprocess

    try:
        if platform.system() == "Windows":
            subprocess.Popen(command, shell=True)
        elif platform.system() == "Darwin" and not shutil.which(command.split()[0]):
            subprocess.Popen(["open", "-a", command])
        else:
            subprocess.Popen(command, shell=True)
        return {"action": "launch", "command": command}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Failed to launch: {exc}"}


def register(mcp) -> None:
    @mcp.tool()
    def gui_screenshot(path: Optional[str] = None, return_base64: bool = False) -> dict:
        """Capture a screenshot; save to a file and/or return it as base64 PNG."""
        return screenshot(path, return_base64)

    @mcp.tool()
    def gui_screen_size() -> dict:
        """Get the primary screen resolution."""
        return screen_size()

    @mcp.tool()
    def gui_mouse_move(x: int, y: int, duration: float = 0.0) -> dict:
        """Move the mouse to absolute screen coordinates."""
        return mouse_move(x, y, duration)

    @mcp.tool()
    def gui_mouse_click(x: Optional[int] = None, y: Optional[int] = None,
                        button: str = "left", clicks: int = 1) -> dict:
        """Click the mouse (left/right/middle), optionally at coordinates. clicks=2 double-clicks."""
        return mouse_click(x, y, button, clicks)

    @mcp.tool()
    def gui_drag_to(x: int, y: int, button: str = "left", duration: float = 0.2) -> dict:
        """Drag from the current cursor position to target coordinates."""
        return drag_to(x, y, button, duration)

    @mcp.tool()
    def gui_type_text(text: str, interval: float = 0.0) -> dict:
        """Type text via simulated keyboard input."""
        return type_text(text, interval)

    @mcp.tool()
    def gui_hotkey(keys: list[str]) -> dict:
        """Press a keyboard shortcut, e.g. ['ctrl','shift','t']."""
        return hotkey(keys)

    @mcp.tool()
    def gui_clipboard_get() -> dict:
        """Read the current system clipboard text."""
        return clipboard_get()

    @mcp.tool()
    def gui_clipboard_set(text: str) -> dict:
        """Set the system clipboard text."""
        return clipboard_set(text)

    @mcp.tool()
    def gui_launch_application(command: str) -> dict:
        """Launch a GUI application by command or path."""
        return launch_application(command)
