import pytest

from app.config import Settings
from app.storage import StorageService


def test_storage_roundtrip(tmp_path):
    s = StorageService(Settings(data_dir=tmp_path))
    key = "grants/abc/hello.pdf"
    s.write_bytes(key, b"hello")
    assert s.exists(key)
    assert s.read_bytes(key) == b"hello"
    s.delete(key)
    assert not s.exists(key)


@pytest.mark.parametrize(
    "bad_key",
    [
        "../etc/passwd",
        "a/../b",
        "/absolute",
        "",
        "   ",
    ],
)
def test_storage_traversal_rejected(tmp_path, bad_key):
    s = StorageService(Settings(data_dir=tmp_path))
    with pytest.raises(ValueError):
        s.write_bytes(bad_key, b"x")
    with pytest.raises(ValueError):
        s.read_bytes(bad_key)
    assert s.exists(bad_key) is False


def test_grant_source_key_sanitizes(tmp_path):
    _ = tmp_path
    k = StorageService.grant_source_key("gid", "../../evil.pdf")
    assert ".." not in k
    assert k.startswith("grants/gid/")


def test_read_missing_raises(tmp_path):
    s = StorageService(Settings(data_dir=tmp_path))
    with pytest.raises(FileNotFoundError):
        s.read_bytes("grants/x/missing.pdf")


def test_delete_prefix_removes_only_selected_grant(tmp_path):
    storage = StorageService(Settings(data_dir=tmp_path))
    storage.write_bytes("grants/g1/a.pdf", b"a")
    storage.write_bytes("grants/g1/b.docx", b"b")
    storage.write_bytes("grants/g2/keep.pdf", b"c")
    storage.delete_prefix("grants/g1")
    assert not storage.exists("grants/g1/a.pdf")
    assert not storage.exists("grants/g1/b.docx")
    assert storage.exists("grants/g2/keep.pdf")
