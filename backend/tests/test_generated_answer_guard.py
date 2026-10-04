from types import SimpleNamespace

from app.services.answers import AnswerItem, enforce_evidence_backed_structured_answer


def _question(q_type: str, question_text: str = "Question"):
    return SimpleNamespace(q_type=q_type, question_text=question_text)


def _evidence(*items: tuple[str, str]):
    return [SimpleNamespace(fact_id=fact_id, text=text) for fact_id, text in items]


def test_unsupported_number_becomes_manual_input():
    result = enforce_evidence_backed_structured_answer(
        _question("number"),
        AnswerItem(question_id="budget", answer_value=8000),
        _evidence(("fact-1", "Mission: provide food assistance"), ("grant_chunk_0", "Amount requested")),
    )
    assert result.answer_value is None
    assert result.needs_manual_input is True


def test_supported_number_is_kept():
    result = enforce_evidence_backed_structured_answer(
        _question("number", "Total amount requested"),
        AnswerItem(question_id="budget", answer_value=8000),
        _evidence(("fact-1", "Request amount: $8,000")),
    )
    assert result.answer_value == 8000
    assert result.needs_manual_input is False


def test_budget_does_not_become_requested_amount():
    result = enforce_evidence_backed_structured_answer(
        _question("number", "Amount requested"),
        AnswerItem(question_id="request", answer_value=25000),
        _evidence(("fact-1", "Annual operating budget 2025: $25,000")),
    )
    assert result.answer_value is None
    assert result.needs_manual_input is True


def test_unsupported_single_choice_becomes_manual_input():
    result = enforce_evidence_backed_structured_answer(
        _question("single_choice"),
        AnswerItem(question_id="area", answer_value="A) Education"),
        _evidence(("fact-1", "Mission: support families facing hardship")),
    )
    assert result.answer_value is None
    assert result.needs_manual_input is True
