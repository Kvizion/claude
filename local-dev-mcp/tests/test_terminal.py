import sys
import time

from tools import terminal


def test_run_captures_stdout(tmp_path):
    result = terminal.run(f'{sys.executable} -c "print(\'hello-world\')"', cwd=str(tmp_path))
    assert result["exit_code"] == 0
    assert "hello-world" in result["stdout"]


def test_run_reports_nonzero_exit(tmp_path):
    result = terminal.run([sys.executable, "-c", "import sys; sys.exit(3)"],
                          cwd=str(tmp_path), shell=False)
    assert result["exit_code"] == 3


def test_run_in_cwd(tmp_path):
    (tmp_path / "marker.txt").write_text("x")
    # List the working directory portably via Python instead of `ls`/`dir`.
    result = terminal.run(
        [sys.executable, "-c", "import os; print('\\n'.join(os.listdir('.')))"],
        cwd=str(tmp_path), shell=False,
    )
    assert "marker.txt" in result["stdout"]


def test_session_lifecycle(tmp_path):
    script = "import time\nfor c in ('a', 'b', 'c'):\n    print(c, flush=True)\ntime.sleep(2)"
    started = terminal.SESSIONS.start([sys.executable, "-u", "-c", script], str(tmp_path), False, None)
    sid = started["session_id"]
    assert started["running"] in (True, False)
    listed = terminal.SESSIONS.list()
    assert any(s["session_id"] == sid for s in listed["sessions"])
    time.sleep(0.4)
    read = terminal.SESSIONS.read(sid)
    assert "a" in read["output"]
    stopped = terminal.SESSIONS.stop(sid)
    assert stopped["action"] == "stopped"
    # session should be gone now
    assert "error" in terminal.SESSIONS.read(sid)


def test_session_interactive_write(tmp_path):
    # A portable echo loop: read stdin lines and write them straight back out.
    script = "import sys\nfor line in sys.stdin:\n    sys.stdout.write(line)\n    sys.stdout.flush()"
    started = terminal.SESSIONS.start([sys.executable, "-u", "-c", script], str(tmp_path), False, None)
    sid = started["session_id"]
    resp = terminal.SESSIONS.write(sid, "ping")
    assert "ping" in resp["output"]
    terminal.SESSIONS.stop(sid, force=True)
