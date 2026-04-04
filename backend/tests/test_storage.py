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
