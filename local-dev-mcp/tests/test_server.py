"""Smoke test that the full server builds and registers a healthy tool set."""

import asyncio

import pytest

mcp = pytest.importorskip("mcp")

from server import build_server  # noqa: E402


def test_server_builds_with_many_tools():
    server = build_server()
    tools = asyncio.run(server.list_tools())
    names = {t.name for t in tools}
    # A representative sample from across the modules.
    expected = {
        "fs_read_file", "fs_write_file", "fs_tree",
        "search_find_files", "search_in_files",
        "terminal_run", "terminal_session_start",
        "git_status", "git_commit",
        "process_list", "system_get_info",
        "net_http_request", "web_fetch",
        "db_sqlite_query", "docker_ps",
        "workspace_detect_project", "ide_open_file",
        "archive_create", "gui_screenshot",
    }
    missing = expected - names
    assert not missing, f"missing tools: {missing}"
    # We register well over 50 tools in total.
    assert len(names) >= 50


def test_browser_html_to_text():
    from tools.browser import html_to_text

    html = "<html><head><style>x{}</style></head><body><h1>Title</h1><p>Hello</p></body></html>"
    text = html_to_text(html)
    assert "Title" in text
    assert "Hello" in text
    assert "{" not in text  # style stripped
