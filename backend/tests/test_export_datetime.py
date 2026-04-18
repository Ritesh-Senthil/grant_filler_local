"""Export timestamp labels by locale (Settings / preferences)."""

from datetime import datetime, timezone

from app.services.export_datetime import format_export_timestamp


def test_iso_includes_utc() -> None:
    dt = datetime(2026, 4, 18, 15, 30, 0, tzinfo=timezone.utc)
    s = format_export_timestamp(dt, "iso")
    assert "2026-04-18" in s
    assert "15:30" in s
    assert s.startswith("Exported:")


def test_en_us_12h() -> None:
    dt = datetime(2026, 4, 18, 15, 30, 0, tzinfo=timezone.utc)
    s = format_export_timestamp(dt, "en-US")
    assert "April" in s
    assert "3:30 PM" in s


def test_en_gb_24h() -> None:
    dt = datetime(2026, 4, 18, 15, 30, 0, tzinfo=timezone.utc)
    s = format_export_timestamp(dt, "en-GB")
    assert "18" in s and "April" in s
    assert "15:30" in s


def test_naive_utc() -> None:
    dt = datetime(2026, 1, 1, 12, 0, 0)  # naive
    s = format_export_timestamp(dt, "iso")
    assert "2026-01-01" in s
    assert "12:00" in s


def test_unknown_locale_falls_back_iso_like() -> None:
    dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    s = format_export_timestamp(dt, "xx-YY")
    assert "2026-01-01" in s
