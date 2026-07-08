"""Network tools: HTTP(S) requests and file downloads.

Implemented on top of the standard library (``urllib``) so no third-party
dependency is required, with a graceful upgrade path to ``requests`` if it is
installed.
"""

from __future__ import annotations

import json as jsonlib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from config import CONFIG
from utils.helpers import human_size, truncate_text


def _check_network_allowed() -> None:
    if not CONFIG.allow_network:
        raise PermissionError("Network access is disabled (LOCAL_DEV_MCP_ALLOW_NETWORK=false).")


def http_request(url: str, method: str = "GET", headers: Optional[dict] = None,
                 body: Optional[str] = None, timeout: int = 30,
                 max_bytes: int = 500_000) -> dict:
    """Perform an HTTP(S) request and return status, headers and body."""
    _check_network_allowed()
    data = body.encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method.upper(),
                                     headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(max_bytes + 1)
            truncated = len(raw) > max_bytes
            raw = raw[:max_bytes]
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("utf-8", errors="replace")
            return {
                "url": url,
                "status": response.status,
                "reason": response.reason,
                "headers": dict(response.headers.items()),
                "body": text,
                "truncated": truncated,
            }
    except urllib.error.HTTPError as exc:
        payload = exc.read(max_bytes).decode("utf-8", errors="replace")
        return {"url": url, "status": exc.code, "reason": exc.reason, "body": payload,
                "error": f"HTTP {exc.code}"}
    except urllib.error.URLError as exc:
        return {"url": url, "error": f"Request failed: {exc.reason}"}


def download_file(url: str, destination: str, timeout: int = 120) -> dict:
    """Download a URL to a local file."""
    _check_network_allowed()
    dest = CONFIG.check_path(destination, write=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response, dest.open("wb") as fh:
            total = 0
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                fh.write(chunk)
                total += len(chunk)
        return {"url": url, "destination": str(dest), "bytes": total, "size_human": human_size(total)}
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        return {"url": url, "error": f"Download failed: {exc}"}


def register(mcp) -> None:
    @mcp.tool()
    def net_http_request(url: str, method: str = "GET", headers: Optional[dict] = None,
                         body: Optional[str] = None, timeout: int = 30) -> dict:
        """Make an HTTP(S) request (GET/POST/PUT/DELETE/...) and return the response."""
        return http_request(url, method, headers, body, timeout)

    @mcp.tool()
    def net_download_file(url: str, destination: str, timeout: int = 120) -> dict:
        """Download a file from a URL to a local path."""
        return download_file(url, destination, timeout)
