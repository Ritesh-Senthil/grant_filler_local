"""Format export timestamps for PDF/DOCX/Markdown from Settings locale (roadmap E)."""

from __future__ import annotations

from datetime import datetime, timezone

_MONTHS_EN = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def format_export_timestamp(utc: datetime, locale: str) -> str:
    """Human-readable *Exported* line. `utc` is normalized to UTC. `locale`: iso | en-US | en-GB."""
    if utc.tzinfo is None:
        utc_aware = utc.replace(tzinfo=timezone.utc)
    else:
        utc_aware = utc.astimezone(timezone.utc)
    u = utc_aware.replace(microsecond=0)
    loc = (locale or "iso").strip() or "iso"
    d = u.date()

    if loc == "iso":
        return f"Exported: {d.isoformat()} {u.strftime('%H:%M:%S')} UTC"

    name = _MONTHS_EN[d.month - 1]
    if loc == "en-US":
        h = u.hour
        m = u.minute
        ampm = "AM" if h < 12 else "PM"
        h12 = h % 12
        if h12 == 0:
            h12 = 12
        return f"Exported: {name} {d.day}, {d.year} at {h12}:{m:02d} {ampm} UTC"
    if loc == "en-GB":
        return f"Exported: {d.day} {name} {d.year} at {u.strftime('%H:%M')} UTC"

    return f"Exported: {d.isoformat()} {u.strftime('%H:%M:%S')} UTC"
