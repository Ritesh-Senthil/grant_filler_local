"""evidence_fact_ids JSON may be malformed; normalization must never raise."""

import pytest

from app.models import Answer
from app.schemas import AnswerRead
from app.services.evidence_ids import normalize_evidence_fact_ids


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, []),
        ([], []),
        (["a", "b"], ["a", "b"]),
        ([1, 2], ["1", "2"]),
        (3, []),
        ("not-list", []),
        (True, []),
    ],
)
def test_normalize_evidence_fact_ids(raw, expected):
    assert normalize_evidence_fact_ids(raw) == expected


def test_normalize_skips_empty_strings() -> None:
    assert normalize_evidence_fact_ids(["x", "", " y "]) == ["x", "y"]


def test_answer_read_from_model_scalar_evidence_does_not_raise() -> None:
    a = Answer(
        grant_id="g",
        question_id="q",
        answer_value="hi",
        reviewed=False,
        needs_manual_input=False,
        evidence_fact_ids=42,  # type: ignore[arg-type]  # simulates bad JSON in DB
    )
    r = AnswerRead.from_model(a)
    assert r.evidence_fact_ids == []
