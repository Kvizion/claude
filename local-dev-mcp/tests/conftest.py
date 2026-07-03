"""Shared pytest fixtures.

Points the server's filesystem/terminal policy at the per-test ``tmp_path`` so
tests never touch the real working tree, and keeps access unrestricted-but-scoped.
"""

import sys
from pathlib import Path

import pytest

# Ensure the project root is importable (config.py, tools/, utils/).
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402


@pytest.fixture(autouse=True)
def scoped_config(tmp_path, monkeypatch):
    """Scope filesystem access to tmp_path and reset capability switches."""
    cfg = config.CONFIG
    monkeypatch.setattr(cfg, "workspace_roots", [tmp_path])
    monkeypatch.setattr(cfg, "default_cwd", tmp_path)
    monkeypatch.setattr(cfg, "allow_write", True)
    monkeypatch.setattr(cfg, "allow_delete", True)
    monkeypatch.setattr(cfg, "allow_terminal", True)
    monkeypatch.setattr(cfg, "allow_network", True)
    monkeypatch.setattr(cfg, "allow_gui", True)
    monkeypatch.setattr(cfg, "allow_database", True)
    return cfg
