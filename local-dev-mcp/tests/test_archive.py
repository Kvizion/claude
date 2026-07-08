from tools import archive


def test_zip_roundtrip(tmp_path):
    src = tmp_path / "data"
    src.mkdir()
    (src / "one.txt").write_text("one")
    (src / "two.txt").write_text("two")

    zip_path = tmp_path / "bundle.zip"
    created = archive.create_archive(str(zip_path), [str(src)], format="zip")
    assert zip_path.exists()
    assert created["format"] == "zip"

    listed = archive.list_archive(str(zip_path))
    assert listed["format"] == "zip"
    assert listed["count"] >= 2

    out = tmp_path / "out"
    extracted = archive.extract_archive(str(zip_path), str(out))
    assert extracted["action"] == "extracted"
    assert (out / "data" / "one.txt").read_text() == "one"


def test_tar_gz_roundtrip(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hello tar")
    tar_path = tmp_path / "bundle.tar.gz"
    archive.create_archive(str(tar_path), [str(f)], format="tar.gz")
    assert tar_path.exists()
    out = tmp_path / "extracted"
    archive.extract_archive(str(tar_path), str(out))
    assert (out / "file.txt").read_text() == "hello tar"


def test_unsupported_format(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x")
    result = archive.create_archive(str(tmp_path / "a.foo"), [str(f)], format="foo")
    assert "error" in result
