"""Lightweight web tools: fetch a page and extract readable text.

This is intentionally dependency-free (uses the standard library only). HTML is
stripped to text with a small regex-based cleaner, which is good enough for
letting the agent read documentation and API responses. For heavy scraping,
install ``requests`` + ``beautifulsoup4`` and extend this module.
"""

from __future__ import annotations

import html
import re
from typing import Optional

from .network import http_request

_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")
_BLANKLINES = re.compile(r"\n\s*\n\s*\n+")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def html_to_text(raw_html: str) -> str:
    without_scripts = _SCRIPT_STYLE.sub(" ", raw_html)
    # Turn common block tags into line breaks before stripping all tags.
    with_breaks = re.sub(r"</(p|div|h[1-6]|li|tr|br|section|article)\s*>", "\n",
                         without_scripts, flags=re.IGNORECASE)
    with_breaks = re.sub(r"<br\s*/?>", "\n", with_breaks, flags=re.IGNORECASE)
    text = _TAG.sub("", with_breaks)
    text = html.unescape(text)
    text = _WS.sub(" ", text)
    text = _BLANKLINES.sub("\n\n", text)
    return text.strip()


def fetch_page(url: str, timeout: int = 30, max_chars: int = 20_000) -> dict:
    """Fetch a web page and return its title and readable text content."""
    response = http_request(url, timeout=timeout, max_bytes=2_000_000)
    if "error" in response and "body" not in response:
        return response
    body = response.get("body", "")
    title_match = _TITLE.search(body)
    title = html.unescape(title_match.group(1)).strip() if title_match else None
    text = html_to_text(body)
    truncated = len(text) > max_chars
    return {
        "url": url,
        "status": response.get("status"),
        "title": title,
        "text": text[:max_chars],
        "truncated": truncated,
    }


def register(mcp) -> None:
    @mcp.tool()
    def web_fetch(url: str, timeout: int = 30, max_chars: int = 20_000) -> dict:
        """Fetch a web page and extract its readable text (good for docs/APIs)."""
        return fetch_page(url, timeout, max_chars)
