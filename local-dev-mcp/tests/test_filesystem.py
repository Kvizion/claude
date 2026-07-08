import pytest

from tools import filesystem as fs


def test_write_and_read(tmp_path):
    target = tmp_path / "hello.txt"
    result = fs.write_file(str(target), "line one\nline two\n")
    assert result["action"] == "created"
    read = fs.read_file(str(target))
    assert "line one" in read["content"]
    assert read["total_lines"] == 2
    assert read["is_binary"] is False


def test_overwrite_reports_action(tmp_path):
    target = tmp_path / "x.txt"
    fs.write_file(str(target), "a")
    result = fs.write_file(str(target), "b")
    assert result["action"] == "overwritten"
    assert fs.read_file(str(target))["content"] == "b"


def test_append(tmp_path):
    target = tmp_path / "log.txt"
    fs.write_file(str(target), "a\n")
    fs.append_file(str(target), "b\n")
    assert fs.read_file(str(target))["content"] == "a\nb"


def test_edit_unique(tmp_path):
    target = tmp_path / "code.py"
    fs.write_file(str(target), "x = 1\ny = 2\n")
    result = fs.edit_file(str(target), "y = 2", "y = 3")
    assert result["action"] == "edited"
    assert "y = 3" in fs.read_file(str(target))["content"]


def test_edit_non_unique_requires_flag(tmp_path):
    target = tmp_path / "dup.txt"
    fs.write_file(str(target), "foo\nfoo\n")
    result = fs.edit_file(str(target), "foo", "bar")
    assert "error" in result
    assert result["matches"] == 2
    ok = fs.edit_file(str(target), "foo", "bar", replace_all=True)
    assert ok["replacements"] == 2


def test_read_offset_limit(tmp_path):
    target = tmp_path / "many.txt"
    fs.write_file(str(target), "\n".join(str(i) for i in range(10)))
    sliced = fs.read_file(str(target), offset=2, limit=3)
    assert sliced["returned_lines"] == 3
    assert sliced["content"].splitlines() == ["2", "3", "4"]


def test_list_and_info(tmp_path):
    (tmp_path / "a.txt").write_text("hi")
    (tmp_path / "sub").mkdir()
    listing = fs.list_directory(str(tmp_path))
    names = {e["name"] for e in listing["entries"]}
    assert {"a.txt", "sub"} <= names
    info = fs.get_file_info(str(tmp_path / "a.txt"))
    assert info["type"] == "file"
    assert info["size_bytes"] == 2


def test_copy_move_delete(tmp_path):
    src = tmp_path / "src.txt"
    fs.write_file(str(src), "data")
    copied = tmp_path / "copy.txt"
    fs.copy_path(str(src), str(copied))
    assert copied.exists()
    moved = tmp_path / "moved.txt"
    fs.move_path(str(copied), str(moved))
    assert moved.exists() and not copied.exists()
    fs.delete_file(str(moved))
    assert not moved.exists()


def test_make_and_remove_directory(tmp_path):
    d = tmp_path / "nested" / "deep"
    fs.make_directory(str(d))
    assert d.is_dir()
    # non-recursive removal on a non-empty tree fails cleanly
    result = fs.remove_directory(str(tmp_path / "nested"))
    assert "error" in result
    fs.remove_directory(str(tmp_path / "nested"), recursive=True)
    assert not (tmp_path / "nested").exists()


def test_tree(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("x=1")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.js").write_text("x")
    tree = fs.build_tree(str(tmp_path))
    assert "pkg" in tree["tree"]
    assert "mod.py" in tree["tree"]
    # node_modules directory shows but is not descended into
    assert "junk.js" not in tree["tree"]


def test_path_policy_blocks_outside(tmp_path):
    with pytest.raises(PermissionError):
        fs.read_file("/etc/passwd")


def test_write_disabled(tmp_path, scoped_config, monkeypatch):
    monkeypatch.setattr(scoped_config, "allow_write", False)
    with pytest.raises(PermissionError):
        fs.write_file(str(tmp_path / "no.txt"), "x")
