import time

from tools import terminal


def test_run_captures_stdout(tmp_path):
    result = terminal.run("echo hello-world", cwd=str(tmp_path))
    assert result["exit_code"] == 0
    assert "hello-world" in result["stdout"]


def test_run_reports_nonzero_exit(tmp_path):
    result = terminal.run("exit 3", cwd=str(tmp_path))
    assert result["exit_code"] == 3


def test_run_in_cwd(tmp_path):
    (tmp_path / "marker.txt").write_text("x")
    result = terminal.run("ls", cwd=str(tmp_path))
    assert "marker.txt" in result["stdout"]


def test_session_lifecycle(tmp_path):
    started = terminal.SESSIONS.start("printf 'a\\nb\\nc\\n'; sleep 2", str(tmp_path), True, None)
    sid = started["session_id"]
    assert started["running"] in (True, False)
    listed = terminal.SESSIONS.list()
    assert any(s["session_id"] == sid for s in listed["sessions"])
    time.sleep(0.3)
    read = terminal.SESSIONS.read(sid)
    assert "a" in read["output"]
    stopped = terminal.SESSIONS.stop(sid)
    assert stopped["action"] == "stopped"
    # session should be gone now
    assert "error" in terminal.SESSIONS.read(sid)


def test_session_interactive_write(tmp_path):
    started = terminal.SESSIONS.start("cat", str(tmp_path), True, None)
    sid = started["session_id"]
    resp = terminal.SESSIONS.write(sid, "ping")
    assert "ping" in resp["output"]
    terminal.SESSIONS.stop(sid, force=True)
