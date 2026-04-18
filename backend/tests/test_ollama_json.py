from types import SimpleNamespace

import json

from app.services.answers import AnswerBatchPayload, normalize_answer_flags
from app.services.json_llm import extract_json


def test_extract_json_plain():
    assert extract_json('{"a":1}') == '{"a":1}'


def test_extract_json_fenced():
    raw = 'Here:\n```json\n{"questions":[]}\n```'
    assert '"questions"' in extract_json(raw)


def test_extract_json_fenced_no_lang():
    raw = "```\n{\"x\": true}\n```"
    assert "true" in extract_json(raw)


def test_normalize_answer_flags_empty_without_model_flag():
    q = SimpleNamespace(q_type="textarea")
    _v, nmi = normalize_answer_flags(q, "", False)
    assert nmi is True


def test_normalize_answer_flags_keeps_filled():
    q = SimpleNamespace(q_type="textarea")
    _v, nmi = normalize_answer_flags(q, "Our mission is …", False)
    assert nmi is False


def test_normalize_answer_flags_number_zero_not_empty():
    q = SimpleNamespace(q_type="number")
    _v, nmi = normalize_answer_flags(q, 0, False)
    assert nmi is False


def test_extract_json_strips_extra_trailing_brace():
    """Models sometimes emit `}}` at the end; Pydantic rejects trailing characters."""
    raw = '{"answers":[{"question_id":"q1","answer_value":"x","needs_manual_input":false,"evidence_fact_ids":[]}]}}'
    snippet = extract_json(raw)
    data = json.loads(snippet)
    assert data["answers"][0]["question_id"] == "q1"
    AnswerBatchPayload.model_validate_json(snippet)


def test_extract_json_prefix_prose():
    raw = 'Here you go: {"answers":[]}'
    assert json.loads(extract_json(raw)) == {"answers": []}
