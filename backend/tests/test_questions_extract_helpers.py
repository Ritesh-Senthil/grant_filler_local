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


def test_dedupe_keeps_choice_without_options_as_text():
    a = ExtractedQuestion(question_text="Pick one", type="single_choice", options=[])
    b = ExtractedQuestion(question_text="Describe", type="textarea")
    out = _dedupe([a, b])
    assert len(out) == 2
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


def test_dedupe_repairs_duplicate_question_ids():
    first = ExtractedQuestion(question_id="1", question_text="Mission?", type="textarea")
    second = ExtractedQuestion(question_id="1", question_text="Budget?", type="textarea")
    out = _dedupe([first, second])
    assert len(out) == 2
    assert len({question.question_id for question in out}) == 2


def test_dedupe_removes_model_supplied_numbering():
    question = ExtractedQuestion(question_text="10. Certification?", type="textarea")
    out = _dedupe([question])
    assert out[0].question_text == "Certification?"


def test_dedupe_normalizes_yes_no_choices():
    question = ExtractedQuestion(
        question_text="3. Are you tax exempt?",
        type="multi_choice",
        options=["Yes", "No"],
    )
    out = _dedupe([question])
    assert out[0].type == "yes_no"
    assert out[0].options == []


def test_dedupe_cleans_yes_no_options_and_checkbox_markers():
    yes_no = ExtractedQuestion(question_text="Tax exempt?", type="yes_no", options=["Yes", "No"])
    checkbox = ExtractedQuestion(question_text="Population?", type="multi_choice", options=["- Youth"])
    out = _dedupe([yes_no, checkbox])
    assert out[0].options == []
    assert out[1].options == ["Youth"]


def test_dedupe_uses_question_wording_to_correct_choice_type():
    question = ExtractedQuestion(
        question_text="4. Which area? (select one)",
        type="multi_choice",
        options=["A", "B"],
    )
    out = _dedupe([question])
    assert out[0].type == "single_choice"
