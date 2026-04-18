"""Unit tests for semantic fact deduplication helpers."""

import math

from app.services.semantic_facts import (
    best_semantic_match_index,
    cosine_similarity,
    fact_embedding_text,
    values_effectively_same,
)


def test_cosine_similarity_identical():
    v = [1.0, 0.0, 0.0]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(cosine_similarity(a, b)) < 1e-6


def test_cosine_similarity_opposite():
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert abs(cosine_similarity(a, b) - (-1.0)) < 1e-6


def test_best_semantic_match_index_picks_highest():
    c = [1.0, 0.0]
    # Three candidates: sims 0.5, 0.95, 0.8 — should pick index 1
    vecs = [
        [math.sqrt(0.5), math.sqrt(0.5)],
        [1.0, 0.0],
        [math.sqrt(0.8), math.sqrt(0.2)],
    ]
    # Normalize vecs[0] dot c ~= 0.707
    idx = best_semantic_match_index(c, vecs, threshold=0.7)
    assert idx == 1


def test_fact_embedding_text_nonempty():
    t = fact_embedding_text("Budget", "1.2M annually")
    assert "Budget" in t and "1.2M" in t


def test_values_effectively_same():
    assert values_effectively_same("Hello world", "hello  world")
    assert values_effectively_same("x", "x")
    assert not values_effectively_same("short", "completely different long text here")
