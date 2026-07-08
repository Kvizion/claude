import json

from tools import workspace


def test_detect_project_type_node(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"react": "^18"}}))
    result = workspace.detect_project_type(str(tmp_path))
    markers = {d["marker"] for d in result["detected"]}
    assert "package.json" in markers


def test_list_dependencies(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"left-pad": "1.0"}, "devDependencies": {"jest": "29"}})
    )
    (tmp_path / "requirements.txt").write_text("requests==2.31\n# comment\nflask\n")
    result = workspace.list_dependencies(str(tmp_path))
    assert "left-pad" in result["dependencies"]["npm"]
    assert "jest" in result["dependencies"]["npm"]
    assert "requests==2.31" in result["dependencies"]["pip"]
    assert "flask" in result["dependencies"]["pip"]


def test_code_stats(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\ny = 2\n")
    (tmp_path / "b.py").write_text("z = 3\n")
    (tmp_path / "c.js").write_text("console.log(1)\n")
    result = workspace.code_stats(str(tmp_path))
    langs = {row["language"]: row for row in result["by_language"]}
    assert langs["Python"]["files"] == 2
    assert langs["Python"]["lines"] == 3
    assert langs["JavaScript"]["files"] == 1


def test_find_todos(tmp_path):
    (tmp_path / "a.py").write_text("# TODO: refactor\nx = 1  # FIXME later\n")
    result = workspace.find_todos(str(tmp_path))
    assert result["count"] == 2
    texts = " ".join(m["text"] for m in result["matches"])
    assert "TODO" in texts and "FIXME" in texts
