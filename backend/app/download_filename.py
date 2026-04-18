"""Sanitized export download names (ISO date; locale deferred until Settings)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import PurePosixPath
from urllib.parse import quote

_FORMAT_EXT = {"qa_pdf": ".pdf", "markdown": ".md", "docx": ".docx"}


def export_format_extension(format_key: str) -> str:
    return _FORMAT_EXT.get(format_key, ".bin")


def build_export_download_filename(grant_name: str | None, format_key: str, when: datetime | None = None) -> str:
    """
    User-facing basename for Save / Content-Disposition.
    `when` must be UTC (default: now UTC).
    """
    ext = export_format_extension(format_key)
    dt = when or datetime.now(timezone.utc)
    date_part = dt.strftime("%Y-%m-%d")
    raw = (grant_name or "").strip() or "grant"
    raw = re.sub(r"\s+", " ", raw)
    stem = raw[:120]
    safe_stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" .") or "grant"
    return f"{safe_stem}_{date_part}{ext}"


def sanitize_content_disposition_filename(
    candidate: str | None,
    *,
    default_stem: str,
    required_ext: str,
) -> str:
    """
    Validate optional ?filename= from the client: single basename, correct extension, safe chars.
    Falls back to default_stem + required_ext.
    """
    ext = required_ext.lower()
    if not ext.startswith("."):
        ext = f".{ext}"

    if not candidate or not candidate.strip():
        return f"{default_stem}{ext}"

    base = PurePosixPath(candidate.strip()).name
    if not base:
        return f"{default_stem}{ext}"

    # Force extension to match stored file type (ignore client mismatch / traversal tricks).
    if not base.lower().endswith(ext.lower()):
        stem = re.sub(r"\.[^.]+$", "", base) or default_stem
        base = f"{stem}{ext}"

    stem_part, dot, suf = base.rpartition(".")
    if not dot:
        return f"{default_stem}{ext}"
    stem_clean = stem_part[:180] if stem_part else default_stem
    stem_clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem_clean).strip(" .") or default_stem
    return f"{stem_clean}.{suf.lower().lstrip('.')}"


def default_export_stem_from_key(file_path: str) -> str:
    """When no filename query: short default from storage key `exports/{id}.pdf`."""
    name = PurePosixPath(file_path).stem
    return name[:16] if name else "export"


def content_disposition_attachment(filename: str) -> str:
    """
    RFC 6266 / 5987: ASCII `filename` + UTF-8 `filename*` for non-Latin grant titles.
    """
    ascii_fallback = re.sub(r"[^\x20-\x7E]+", "_", filename).strip() or "download"
    if len(ascii_fallback) > 170:
        ascii_fallback = ascii_fallback[:170]
    ascii_fallback = ascii_fallback.replace("\\", "_").replace('"', "_")
    quoted_utf8 = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quoted_utf8}"
