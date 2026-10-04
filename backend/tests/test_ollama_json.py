from types import SimpleNamespace

import json
import asyncio

from pydantic import BaseModel

from app.services.answers import AnswerBatchPayload, normalize_answer_flags
from app.services.json_llm import extract_json
from app.services.json_llm import chat_json_with_repair


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


def test_json_repair_repeats_schema_and_invalid_response():
    class Payload(BaseModel):
        questions: list[str]

    calls: list[tuple[str, str]] = []

    async def chat(system: str, user: str) -> str:
        calls.append((system, user))
        if len(calls) == 1:
            return '{"page_1":{"question_1":"Name?"}}'
        return '{"questions":["Name?"]}'

    result = asyncio.run(chat_json_with_repair(chat, "Original schema instructions", "Document", Payload))
    assert result.questions == ["Name?"]
    assert "Original schema instructions" in calls[1][0]
    assert "Required JSON Schema" in calls[1][0]
    assert "page_1" in calls[1][1]
