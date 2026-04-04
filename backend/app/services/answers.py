import json
from typing import Any

from pydantic import BaseModel, Field

from app.models import Organization, Question
from app.services.ollama import OllamaClient
from app.services.retrieve import retrieve_evidence


class AnswerItem(BaseModel):
    question_id: str
    answer_value: Any = None
    needs_manual_input: bool = False
    evidence_fact_ids: list[str] = Field(default_factory=list)


class AnswerBatchPayload(BaseModel):
    answers: list[AnswerItem]


def _answer_is_effectively_empty(val: Any, q_type: str) -> bool:
    """True when there is nothing meaningful to show (model may omit needs_manual_input)."""
    if val is None:
        return True
    if isinstance(val, str):
        s = val.strip()
        return not s or s.upper() == "INSUFFICIENT_INFO"
    if isinstance(val, list):
        return len(val) == 0
    if isinstance(val, (int, float)) and q_type == "number":
        return False
    return False


def normalize_answer_flags(q: Question, answer_value: Any, needs_manual_input: bool) -> tuple[Any, bool]:
    """If the draft is empty, always set needs_manual_input so the UI shows 'Needs manual input'."""
    if needs_manual_input:
        return answer_value, True
    if _answer_is_effectively_empty(answer_value, q.q_type):
        return answer_value, True
    return answer_value, False


ANSWER_SYSTEM = """You draft grant application answers using ONLY the evidence provided.
Rules:
- First person plural (we/our organization) where appropriate.
- Do NOT invent specific facts (numbers, dates, names, programs) not present in evidence.
- If evidence is insufficient to answer responsibly, set answer_value to the string "INSUFFICIENT_INFO" for text types,
  or null with needs_manual_input true.
- Match question type exactly:
  - yes_no: answer "Yes" or "No" only when supported by evidence; else INSUFFICIENT_INFO.
  - single_choice: answer_value must be EXACTLY one string from options.
  - multi_choice: answer_value must be a JSON array of strings, subset of options.
  - number: numeric value or INSUFFICIENT_INFO.
  - date: ISO date YYYY-MM-DD or INSUFFICIENT_INFO.
  - text/textarea/other: concise paragraph or INSUFFICIENT_INFO.
- Output JSON only: {"answers":[{"question_id":"","answer_value":...,"needs_manual_input":false,"evidence_fact_ids":[]}]}
"""


def _evidence_block(evs: list) -> str:
    lines = []
    for e in evs:
        lines.append(f"- [{e.fact_id}] {e.text}")
    return "\n".join(lines)


async def generate_answers_batch(
    ollama: OllamaClient,
    org: Organization,
    facts: list,
    questions: list[Question],
) -> list[AnswerItem]:
    if not questions:
        return []
    items: list[AnswerItem] = []
    for q in questions:
        evs = retrieve_evidence(q.question_text, org, facts, top_k=10)
        user = (
            f"Question ID: {q.question_id}\n"
            f"Question: {q.question_text}\n"
            f"Type: {q.q_type}\n"
            f"Options: {json.dumps(q.options or [])}\n"
            f"Char limit: {q.char_limit}\n\n"
            f"Evidence:\n{_evidence_block(evs)}\n\n"
            "Return JSON: {\"answers\":[{\"question_id\":...}]}"
        )
        payload = await ollama.chat_json(ANSWER_SYSTEM, user, AnswerBatchPayload)
        if payload.answers:
            a = payload.answers[0]
            a.question_id = q.question_id
            if not a.evidence_fact_ids and evs:
                a.evidence_fact_ids = [e.fact_id for e in evs[:5]]
            items.append(a)
        else:
            items.append(
                AnswerItem(
                    question_id=q.question_id,
                    answer_value="INSUFFICIENT_INFO",
                    needs_manual_input=True,
                    evidence_fact_ids=[e.fact_id for e in evs[:5]],
                )
            )
    return items
