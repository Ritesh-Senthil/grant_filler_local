import re
from pathlib import Path

from app.config import Settings

_ORG_ID_RE = re.compile(r"[^a-zA-Z0-9._-]+")


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

    def delete_prefix(self, prefix: str) -> None:
        """Delete files below a storage prefix without allowing traversal."""
        try:
            base = self._safe_key(prefix)
        except ValueError:
            return
        if base.is_file():
            base.unlink()
            return
        if not base.is_dir():
            return
        for path in sorted(base.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        base.rmdir()

    def delete_exports(self, grant_id: str) -> None:
        safe_id = re.sub(r"[^a-zA-Z0-9._-]", "_", grant_id)[:128]
        for path in self.root.glob(f"exports/{safe_id}.*"):
            if path.is_file():
                path.unlink()

    @staticmethod
    def grant_source_key(grant_id: str, filename: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9._-]", "_", Path(filename).name)[:200]
        return f"grants/{grant_id}/{safe}"

    @staticmethod
    def export_key(grant_id: str, ext: str = "pdf") -> str:
        return f"exports/{grant_id}.{ext}"

    @staticmethod
    def org_banner_key(org_id: str, ext: str) -> str:
        """Storage key for an org header banner (single file per org; ext is jpg/png/webp/gif)."""
        parts = [p for p in _ORG_ID_RE.sub("_", org_id).strip("_").split("/") if p]
        safe = "_".join(parts)[:64] if parts else "org"
        e = (ext or "").lower().lstrip(".")
        if e == "jpeg":
            e = "jpg"
        if e not in ("jpg", "png", "webp", "gif"):
            raise ValueError("Unsupported banner image type")
        return f"orgs/{safe}/banner.{e}"
