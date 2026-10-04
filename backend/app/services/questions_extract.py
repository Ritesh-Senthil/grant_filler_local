import asyncio
import re
import uuid
from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import BaseModel, Field

from app.services.llm_types import LlmClient


class ExtractedQuestion(BaseModel):
    question_id: str = ""
    question_text: str
    type: Literal[
        "text",
        "textarea",
        "single_choice",
        "multi_choice",
        "yes_no",
        "number",
        "date",
        "other",
    ] = "textarea"
    options: list[str] = Field(default_factory=list)
    required: bool = False
    char_limit: int | None = None


class QuestionListPayload(BaseModel):
    questions: list[ExtractedQuestion]


SYSTEM = """You extract grant or application form questions from document text.
Return JSON only matching this schema:
{"questions":[{"question_id":"","question_text":"","type":"textarea|text|single_choice|multi_choice|yes_no|number|date|other","options":[],"required":false,"char_limit":null}]}
Rules:
- question_text is the full question as written.
- Do not include a leading question number or letter in question_text; the application numbers questions from their saved order.
- Extract EVERY numbered or lettered prompt that expects a response, including certifications and attestations.
- For choice types, fill options with exact choice strings if present; else empty array.
- A prompt with exactly Yes / No choices is type yes_no, not multi_choice.
- A free-text or "other" response is type textarea unless it clearly requests a short answer.
- If no clear questions exist in this chunk, return {"questions":[]}.
- Do not invent questions not supported by the text.
"""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


_LEADING_QUESTION_NUMBER = re.compile(
    r"^\s*(?:question\s+)?(?:\d+(?:\.\d+)*[a-z]?|[a-z])\s*[.):-]\s+",
    re.IGNORECASE,
)


def _normalize_question(q: ExtractedQuestion) -> ExtractedQuestion:
    q.question_text = _LEADING_QUESTION_NUMBER.sub("", q.question_text or "").strip()
    q.options = [re.sub(r"^\s*[-•]\s*", "", option).strip() for option in q.options if option.strip()]
    normalized_options = {_norm(option) for option in q.options}
    if q.type in ("single_choice", "multi_choice") and normalized_options == {"yes", "no"}:
        q.type = "yes_no"
        q.options = []
    elif q.type == "yes_no":
        q.options = []
    lowered = q.question_text.lower()
    if q.options and any(phrase in lowered for phrase in ("select one", "choose one", "pick one")):
        q.type = "single_choice"
    elif q.options and any(phrase in lowered for phrase in ("select all", "choose all", "pick any")):
        q.type = "multi_choice"
    return q


def _dedupe(questions: list[ExtractedQuestion]) -> list[ExtractedQuestion]:
    seen: set[str] = set()
    used_ids: set[str] = set()
    out: list[ExtractedQuestion] = []
    for q in questions:
        q = _normalize_question(q)
        key = _norm(q.question_text)
        if not key or key in seen:
            continue
        seen.add(key)
        if not q.question_id or q.question_id in used_ids:
            q.question_id = f"q_{uuid.uuid4().hex[:12]}"
        if q.type in ("single_choice", "multi_choice") and not q.options:
            # Keeping the prompt is safer than silently losing it. The user can answer it
            # as text and correct its type/options in the workspace.
            q.type = "textarea"
        used_ids.add(q.question_id)
        out.append(q)
    return out


def _validate_nonempty(questions: list[ExtractedQuestion]) -> list[ExtractedQuestion]:
    out: list[ExtractedQuestion] = []
    for q in questions:
        if not (q.question_text or "").strip():
            continue
        if q.type in ("single_choice", "multi_choice") and not q.options:
            q.type = "textarea"
        out.append(q)
    return out


async def extract_questions_from_chunks(
    llm: LlmClient,
    chunks: list[str],
    *,
    max_concurrency: int = 3,
    on_chunk_complete: Callable[[int, int], Awaitable[None]] | None = None,
) -> list[ExtractedQuestion]:
    """Extract questions per text chunk. Chunks are processed in parallel (bounded) to reduce wall time."""
    if not chunks:
        return []

    n = len(chunks)
    conc = max(1, min(max_concurrency, n))

    async def run_one(i: int, chunk: str) -> list[ExtractedQuestion]:
        user = f"Chunk {i+1}/{n}:\n\n{chunk}"
        payload = await llm.chat_json(SYSTEM, user, QuestionListPayload)
        return list(payload.questions)

    async def bump(done: int) -> None:
        if on_chunk_complete:
            await on_chunk_complete(done, n)

    if conc == 1:
        merged: list[ExtractedQuestion] = []
        for i, chunk in enumerate(chunks):
            merged.extend(await run_one(i, chunk))
            await bump(i + 1)
    else:
        sem = asyncio.Semaphore(conc)
        lock = asyncio.Lock()
        completed = 0

        async def bounded(i: int, chunk: str) -> list[ExtractedQuestion]:
            nonlocal completed
            async with sem:
                out = await run_one(i, chunk)
            async with lock:
                completed += 1
                done = completed
            await bump(done)
            return out

        parts = await asyncio.gather(*(bounded(i, c) for i, c in enumerate(chunks)))
        merged = []
        for part in parts:
            merged.extend(part)

    merged = _dedupe(merged)
    merged = _validate_nonempty(merged)
    return merged
