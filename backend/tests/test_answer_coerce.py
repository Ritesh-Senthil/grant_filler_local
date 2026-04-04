import pytest

from app.models import Question
from app.services.answer_coerce import coerce_answer_value


def _q(**kwargs) -> Question:
    defaults = dict(
        grant_id="g",
        question_id="q1",
        question_text="?",
        q_type="textarea",
        sort_order=0,
    )
    defaults.update(kwargs)
    return Question(**defaults)


def test_yes_no_normalizes():
    q = _q(q_type="yes_no")
    assert coerce_answer_value(q, "yes") == "Yes"
    assert coerce_answer_value(q, "No") == "No"
    assert coerce_answer_value(q, "") == ""


def test_yes_no_rejects_garbage():
    q = _q(q_type="yes_no")
    with pytest.raises(ValueError, match="Yes or No"):
        coerce_answer_value(q, "maybe")


def test_single_choice_must_match_options():
    q = _q(q_type="single_choice", options=["A", "B"])
    assert coerce_answer_value(q, "A") == "A"
    with pytest.raises(ValueError, match="one of"):
        coerce_answer_value(q, "C")


def test_multi_choice_subset():
    q = _q(q_type="multi_choice", options=["A", "B"])
    assert coerce_answer_value(q, ["B", "A"]) == ["B", "A"]


def test_multi_choice_invalid_option():
    q = _q(q_type="multi_choice", options=["A"])
    with pytest.raises(ValueError, match="Invalid"):
        coerce_answer_value(q, ["X"])


def test_number_parses():
    q = _q(q_type="number")
    assert coerce_answer_value(q, "3.5") == 3.5
    assert coerce_answer_value(q, 2) == 2
    assert coerce_answer_value(q, "") == ""


def test_date_format():
    q = _q(q_type="date")
    assert coerce_answer_value(q, "2026-01-15") == "2026-01-15"
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        coerce_answer_value(q, "01/15/2026")
