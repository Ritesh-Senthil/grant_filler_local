"""Semantic deduplication for organization facts (embeddings + cosine similarity)."""

from __future__ import annotations

import math
import re

from app.models import Fact


_WS = re.compile(r"\s+")


def fact_embedding_text(key: str, value: str) -> str:
    """Single string for embedding: emphasizes label + content for similarity."""
    k = (key or "").strip()
    v = (value or "").strip()
    if not k and not v:
        return ""
    if not v:
        return f"Organization fact label: {k}"
    return f"Organization fact: {k}. Details: {v}"


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        na += x * x
        nb += y * y
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def norm_fact_value(s: str) -> str:
    return _WS.sub(" ", (s or "").strip().lower())


def values_effectively_same(a: str, b: str) -> bool:
    """True when two fact values are duplicates for merge/skip purposes."""
    x = norm_fact_value(a)
    y = norm_fact_value(b)
    if not x and not y:
        return True
    if x == y:
        return True
    if len(x) > 12 and len(y) > 12 and (x in y or y in x):
        return True
    return False


def best_semantic_match_index(
    candidate: list[float],
    existing_vectors: list[list[float]],
    threshold: float,
) -> int | None:
    """Index of existing fact with highest cosine similarity among those >= threshold."""
    best_i: int | None = None
    best_sim = -1.0
    for i, ev in enumerate(existing_vectors):
        sim = cosine_similarity(candidate, ev)
        if sim >= threshold and sim > best_sim:
            best_sim = sim
            best_i = i
    return best_i
