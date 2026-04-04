"""Unit tests for dedupe / validation (no LLM)."""

from app.services.questions_extract import (
    ExtractedQuestion,
    _dedupe,
    _validate_nonempty,
)


def test_dedupe_drops_duplicate_text():
    a = ExtractedQuestion(question_text="  What is your mission?  ", type="textarea")
    b = ExtractedQuestion(question_text="  What is your mission?  ", type="textarea")
    out = _dedupe([a, b])
    assert len(out) == 1


def test_dedupe_case_insensitive():
    a = ExtractedQuestion(question_text="What is your mission?", type="textarea")
    b = ExtractedQuestion(question_text="what is your mission?", type="textarea")
    out = _dedupe([a, b])
    assert len(out) == 1


def test_dedupe_drops_choice_without_options():
    a = ExtractedQuestion(question_text="Pick one", type="single_choice", options=[])
    b = ExtractedQuestion(question_text="Describe", type="textarea")
    out = _dedupe([a, b])
    assert len(out) == 1
    assert out[0].type == "textarea"


def test_dedupe_keeps_choice_with_options():
    a = ExtractedQuestion(
        question_text="Pick",
        type="single_choice",
        options=["A", "B"],
    )
    out = _dedupe([a])
    assert len(out) == 1


def test_validate_nonempty_strips_empty_questions():
    a = ExtractedQuestion(question_text="   ", type="textarea")
    b = ExtractedQuestion(question_text="Real?", type="textarea")
    out = _validate_nonempty([a, b])
    assert len(out) == 1


def test_dedupe_assigns_question_id():
    a = ExtractedQuestion(question_text="Only question", type="textarea", question_id="")
    out = _dedupe([a])
    assert out[0].question_id.startswith("q_")
