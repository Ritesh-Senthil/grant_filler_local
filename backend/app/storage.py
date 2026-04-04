import re
from pathlib import Path

from app.config import Settings


class StorageService:
    """Blob storage under data_dir/blobs with traversal-safe keys."""

    def __init__(self, settings: Settings):
        self.root = (settings.data_dir / "blobs").resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_key(self, key: str) -> Path:
        normalized = key.strip().replace("\\", "/")
        if ".." in normalized or normalized.startswith("/"):
            raise ValueError("Invalid file key")
        parts = [p for p in normalized.split("/") if p and p != "."]
        if not parts:
            raise ValueError("Empty file key")
        candidate = self.root.joinpath(*parts).resolve()
        if not str(candidate).startswith(str(self.root)):
            raise ValueError("Path escapes storage root")
        return candidate

    def write_bytes(self, key: str, data: bytes, suffix: str | None = None) -> str:
        path = self._safe_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def read_bytes(self, key: str) -> bytes:
        path = self._safe_key(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        try:
            return self._safe_key(key).is_file()
        except ValueError:
            return False

    def delete(self, key: str) -> None:
        try:
            p = self._safe_key(key)
            if p.is_file():
                p.unlink()
        except ValueError:
            pass

    @staticmethod
    def grant_source_key(grant_id: str, filename: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9._-]", "_", Path(filename).name)[:200]
        return f"grants/{grant_id}/{safe}"

    @staticmethod
    def export_key(grant_id: str, ext: str = "pdf") -> str:
        return f"exports/{grant_id}.{ext}"
