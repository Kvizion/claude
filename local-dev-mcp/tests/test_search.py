from tools import search


def _seed(tmp_path):
    (tmp_path / "a.py").write_text("import os\n# TODO fix me\nprint('hello')\n")
    (tmp_path / "b.txt").write_text("nothing interesting\n")
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "c.py").write_text("def hello():\n    return 'world'\n")


def test_find_files(tmp_path):
    _seed(tmp_path)
    result = search.find_files("*.py", str(tmp_path))
    assert result["count"] == 2
    assert all(f.endswith(".py") for f in result["files"])


def test_search_text_finds_matches(tmp_path):
    _seed(tmp_path)
    result = search.search_text("hello", str(tmp_path), is_regex=False)
    files = {m["file"] for m in result["matches"]}
    assert any(f.endswith("a.py") for f in files)
    assert any(f.endswith("c.py") for f in files)


def test_search_text_glob_filter(tmp_path):
    _seed(tmp_path)
    result = search.search_text("nothing", str(tmp_path), glob="*.txt", is_regex=False)
    assert result["count"] == 1
    assert result["matches"][0]["file"].endswith("b.txt")


def test_search_regex(tmp_path):
    _seed(tmp_path)
    result = search.search_text(r"def \w+\(", str(tmp_path), is_regex=True)
    assert result["count"] >= 1
