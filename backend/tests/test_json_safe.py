"""JSON safety for API payloads (no NaN/Inf in HTTP JSON)."""

import json

import pytest
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.models import Answer
from app.schemas import AnswerRead
from app.services.json_safe import sanitize_answer_value_for_api


def test_sanitize_strips_nan_float() -> None:
    raw = {"x": float("nan"), "y": 1.0}
    out = sanitize_answer_value_for_api(raw)
    JSONResponse(content=jsonable_encoder(AnswerRead(question_id="q", answer_value=out).model_dump()))


def test_answer_read_from_model_nan_does_not_break_json() -> None:
    a = Answer(
        grant_id="g",
        question_id="q",
        answer_value=float("nan"),
        reviewed=False,
        needs_manual_input=False,
        evidence_fact_ids=[],
    )
    payload = AnswerRead.from_model(a).model_dump()
    JSONResponse(content=jsonable_encoder(payload))
    assert payload["answer_value"] is None


def test_json_dumps_strict_rejects_nan_without_sanitize() -> None:
    with pytest.raises(ValueError):
        json.dumps({"a": float("nan")}, allow_nan=False)
