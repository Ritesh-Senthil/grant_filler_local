"""Normalize evidence_fact_ids from JSON columns (LLM output or legacy data can be malformed)."""

from typing import Any


def normalize_evidence_fact_ids(raw: Any) -> list[str]:
    """Always return a list of non-empty strings. Never call list() on arbitrary scalars (can throw)."""
    if raw is None:
        return []
    if isinstance(raw, list):
        out: list[str] = []
        for x in raw:
            if x is None:
                continue
            s = str(x).strip()
            if s:
                out.append(s)
        return out
    return []
