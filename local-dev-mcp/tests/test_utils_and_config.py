import sys

import pytest

import config as config_module
from utils.helpers import human_size, run_command, split_command, truncate_text


def test_human_size():
    assert human_size(0) == "0 B"
    assert human_size(1023) == "1023 B"
    assert human_size(1024) == "1.0 KB"
    assert human_size(1024 * 1024) == "1.0 MB"


def test_truncate_text():
    text = "a" * 100
    truncated, was_truncated = truncate_text(text, 10)
    assert was_truncated is True
    assert len(truncated.encode("utf-8")) <= 10
    unchanged, flag = truncate_text("short", 100)
    assert flag is False and unchanged == "short"


def test_split_command():
    assert split_command("git status", shell=False) == ["git", "status"]
    assert split_command("echo hi", shell=True) == "echo hi"


def test_run_command_success():
    result = run_command([sys.executable, "-c", "print('hi')"])
    assert result["exit_code"] == 0
    assert "hi" in result["stdout"]


def test_run_command_missing_binary():
    result = run_command(["definitely-not-a-real-binary-xyz"])
    assert result["exit_code"] == 127
    assert "not found" in result["stderr"].lower()


def test_run_command_timeout():
    result = run_command([sys.executable, "-c", "import time; time.sleep(5)"], timeout=1)
    assert result["timed_out"] is True


def test_config_path_policy(tmp_path):
    cfg = config_module.Config(workspace_roots=[tmp_path])
    inside = cfg.check_path(tmp_path / "a.txt")
    assert str(inside).startswith(str(tmp_path))
    with pytest.raises(PermissionError):
        cfg.check_path("/etc/hosts")


def test_config_unrestricted_when_no_roots():
    cfg = config_module.Config(workspace_roots=[])
    # No exception: unrestricted mode allows any absolute path.
    assert cfg.is_allowed(cfg.resolve("/tmp/anywhere")) is True


def test_config_write_guard(tmp_path):
    cfg = config_module.Config(workspace_roots=[tmp_path], allow_write=False)
    with pytest.raises(PermissionError):
        cfg.check_path(tmp_path / "x", write=True)


def test_is_allowed_subpath_and_sibling(tmp_path):
    cfg = config_module.Config(workspace_roots=[tmp_path / "root"])
    assert cfg.is_allowed(tmp_path / "root" / "sub" / "f.txt") is True
    # A sibling that merely shares a name prefix must NOT be allowed.
    assert cfg.is_allowed(tmp_path / "rootother" / "f.txt") is False


def test_read_roots_file(tmp_path):
    listing = tmp_path / "allowed.txt"
    listing.write_text(
        f"# my allowed folders\n{tmp_path / 'a'}\n\n\"{tmp_path / 'b'}\"\n",
        encoding="utf-8",
    )
    roots = config_module._read_roots_file(listing)
    assert {r.name for r in roots} == {"a", "b"}


def test_load_roots_merges_env_and_file(tmp_path, monkeypatch):
    listing = tmp_path / "allowed.txt"
    listing.write_text(str(tmp_path / "from_file") + "\n", encoding="utf-8")
    monkeypatch.setenv("LOCAL_DEV_MCP_ROOTS", str(tmp_path / "from_env"))
    monkeypatch.setenv("LOCAL_DEV_MCP_ROOTS_FILE", str(listing))
    monkeypatch.setattr(config_module, "DEFAULT_ROOTS_FILE", tmp_path / "does_not_exist.txt")
    names = {r.name for r in config_module._load_roots()}
    assert {"from_env", "from_file"} <= names
