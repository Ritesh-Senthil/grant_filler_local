"""Export download filename helpers."""

import re

from app.download_filename import (
    build_export_download_filename,
    content_disposition_attachment,
    default_export_stem_from_key,
    sanitize_content_disposition_filename,
)


def test_build_export_download_filename_basic():
    name = build_export_download_filename("My Grant", "qa_pdf")
    assert name.endswith(".pdf")
    assert name.startswith("My Grant_")
    assert re.search(r"_\d{4}-\d{2}-\d{2}\.pdf$", name)


def test_build_export_download_filename_empty_name():
    name = build_export_download_filename(None, "markdown")
    assert name.startswith("grant_")
    assert name.endswith(".md")


def test_build_export_download_filename_sanitizes_path_chars():
    name = build_export_download_filename('Bad<>:"/\\|?*', "docx")
    assert "<" not in name
    assert name.endswith(".docx")


def test_sanitize_forces_extension():
    got = sanitize_content_disposition_filename(
        "evil.exe",
        default_stem="z",
        required_ext=".pdf",
    )
    assert got.endswith(".pdf")
    assert "exe" not in got.lower()


def test_sanitize_strips_paths():
    got = sanitize_content_disposition_filename(
        "../../../etc/passwd.pdf",
        default_stem="z",
        required_ext=".pdf",
    )
    assert ".." not in got
    assert got == "passwd.pdf" or got.endswith(".pdf")


def test_default_stem_from_key_truncates():
    long_id = "0123456789abcdef0123456789abcdef"
    assert default_export_stem_from_key(f"exports/{long_id}.pdf") == long_id[:16]


def test_content_disposition_has_attachment_and_utf8():
    cd = content_disposition_attachment("Résumé_2026-04-17.pdf")
    assert cd.startswith("attachment;")
    assert "filename*=" in cd

