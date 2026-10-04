import json
import asyncio
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field

from app.models import Question
from app.services.llm_types import Embedder, LlmClient
from app.services.retrieve import DEFAULT_GRANT_CHUNK_CAP, build_evidence_index, retrieve_evidence


class AnswerItem(BaseModel):
    question_id: str
    # Keep the schema concrete: Ollama's structured-output endpoint rejects an
    # unconstrained JSON Schema property (Pydantic's schema for plain Any).
    answer_value: str | int | float | bool | list[str] | None = None
    needs_manual_input: bool = False
    evidence_fact_ids: list[str] = Field(default_factory=list)


class AnswerBatchPayload(BaseModel):
    answers: list[AnswerItem]


def answer_value_is_effectively_empty(val: Any, q_type: str) -> bool:
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
    if answer_value_is_effectively_empty(answer_value, q.q_type):
        return answer_value, True
    return answer_value, False


def _org_evidence_texts(evidence: list) -> list[str]:
    """Application chunks describe the form, not facts about the applicant."""
    return [e.text for e in evidence if not str(e.fact_id).startswith("grant_chunk_")]


def _choice_text(value: str) -> str:
    return re.sub(r"^\s*[a-z0-9]+[).:-]\s*", "", value, flags=re.IGNORECASE).strip().lower()


def _number_in_text(value: int | float, text: str) -> bool:
    try:
        wanted = Decimal(str(value))
    except InvalidOperation:
        return False
    for token in re.findall(r"(?<![\w.])-?\$?\d[\d,]*(?:\.\d+)?", text):
        try:
            if Decimal(token.replace("$", "").replace(",", "")) == wanted:
                return True
        except InvalidOperation:
            continue
    return False


def _number_fact_matches_question(q: Question, value: int | float, text: str) -> bool:
    """Require a numeric fact to describe the same thing the form asks for.

    Matching a number alone is not enough: an annual budget must not become a
    grant request just because both happen to be dollar amounts.
    """
    if not _number_in_text(value, text):
        return False
    question = (q.question_text or "").lower()
    fact = text.lower()
    asks_for_request_amount = bool(
        re.search(r"\b(amount|funding)\b[^.\n]{0,30}\brequest(?:ed)?\b", question)
        or re.search(r"\brequest(?:ed)?\b[^.\n]{0,30}\b(amount|funding)\b", question)
    )
    if asks_for_request_amount:
        return bool(
            re.search(r"\b(amount|funding)\b[^.\n]{0,30}\brequest(?:ed)?\b", fact)
            or re.search(r"\brequest(?:ed)?\b[^.\n]{0,30}\b(amount|funding)\b", fact)
        )

    ignored = {
        "a", "an", "and", "for", "from", "how", "in", "is", "most", "of", "on", "or", "the", "this", "to", "what",
    }
    keywords = {
        token
        for token in re.findall(r"[a-z]{3,}", question)
        if token not in ignored
    }
    return bool(keywords & set(re.findall(r"[a-z]{3,}", fact)))


def enforce_evidence_backed_structured_answer(q: Question, item: AnswerItem, evidence: list) -> AnswerItem:
    """Do not let a draft invent a date, number, or multiple-choice selection.

    The application text itself is useful to retrieve wording and options, but it
    does not establish information about the nonprofit. These structured fields
    therefore require support in a saved organization fact.
    """
    value = item.answer_value
    fact_texts = _org_evidence_texts(evidence)
    if q.q_type == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
        if not any(_number_fact_matches_question(q, value, text) for text in fact_texts):
            return AnswerItem(question_id=item.question_id, answer_value=None, needs_manual_input=True)
    elif q.q_type == "date" and isinstance(value, str) and value.strip():
        if not any(value.strip() in text for text in fact_texts):
            return AnswerItem(question_id=item.question_id, answer_value=None, needs_manual_input=True)
    elif q.q_type == "single_choice" and isinstance(value, str) and value.strip():
        choice = _choice_text(value)
        if not any(choice and choice in text.lower() for text in fact_texts):
            return AnswerItem(question_id=item.question_id, answer_value=None, needs_manual_input=True)
    elif q.q_type == "multi_choice" and isinstance(value, list):
        supported = [
            option
            for option in value
            if isinstance(option, str)
            and any(_choice_text(option) and _choice_text(option) in text.lower() for text in fact_texts)
        ]
        if len(supported) != len(value):
            return AnswerItem(
                question_id=item.question_id,
                answer_value=supported,
                needs_manual_input=True,
                evidence_fact_ids=item.evidence_fact_ids,
            )
    return item


ANSWER_SYSTEM = """You draft grant application answers using ONLY the evidence provided.
Evidence may include:
- Rows labeled [Application source — chunk N]: text from this grant's uploaded file or imported web page.
- Organization key/value facts (mission, address, programs, etc.) that the nonprofit has saved.
Rules:
- First person plural (we/our organization) where appropriate.
- Do NOT invent specific facts (numbers, dates, names, programs) not present in evidence.
- Prefer details from [Application source] chunks when they directly address the question (instructions, limits, funder-specific wording).
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
    llm: LlmClient,
    embedder: Embedder,
    facts: list,
    questions: list[Question],
    *,
    grant_chunks: list[str] | None = None,
    grant_chunk_cap: int | None = None,
    max_concurrency: int = 2,
) -> list[AnswerItem]:
    if not questions:
        return []
    cap = grant_chunk_cap if grant_chunk_cap is not None else DEFAULT_GRANT_CHUNK_CAP
    evidence_index = await build_evidence_index(
        embedder,
        facts,
        grant_chunks=grant_chunks,
        grant_chunk_cap=cap,
    )
    semaphore = asyncio.Semaphore(max(1, min(max_concurrency, len(questions))))

    async def generate_one(q: Question) -> AnswerItem:
        async with semaphore:
            return await _generate_one(q)

    async def _generate_one(q: Question) -> AnswerItem:
        evs = await retrieve_evidence(
            embedder,
            q.question_text,
            facts,
            top_k=12,
            grant_chunks=grant_chunks,
            grant_chunk_cap=cap,
            index=evidence_index,
        )
        user = (
            f"Question ID: {q.question_id}\n"
            f"Question: {q.question_text}\n"
            f"Type: {q.q_type}\n"
            f"Options: {json.dumps(q.options or [])}\n"
            f"Char limit: {q.char_limit}\n\n"
            f"Evidence:\n{_evidence_block(evs)}\n\n"
            "Return JSON: {\"answers\":[{\"question_id\":...}]}"
        )
        payload = await llm.chat_json(ANSWER_SYSTEM, user, AnswerBatchPayload)
        if payload.answers:
            a = payload.answers[0]
            a.question_id = q.question_id
            allowed_ids = {e.fact_id for e in evs}
            a.evidence_fact_ids = [eid for eid in a.evidence_fact_ids if eid in allowed_ids]
            return enforce_evidence_backed_structured_answer(q, a, evs)
        else:
            return AnswerItem(
                question_id=q.question_id,
                answer_value="INSUFFICIENT_INFO",
                needs_manual_input=True,
                evidence_fact_ids=[],
            )
    return list(await asyncio.gather(*(generate_one(question) for question in questions)))
