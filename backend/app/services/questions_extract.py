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
- For choice types, fill options with exact choice strings if present; else empty array.
- If no clear questions exist in this chunk, return {"questions":[]}.
- Do not invent questions not supported by the text.
"""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _dedupe(questions: list[ExtractedQuestion]) -> list[ExtractedQuestion]:
    seen: set[str] = set()
    out: list[ExtractedQuestion] = []
    for q in questions:
        key = _norm(q.question_text)
        if not key or key in seen:
            continue
        seen.add(key)
        if not q.question_id:
            q.question_id = f"q_{uuid.uuid4().hex[:12]}"
        if q.type in ("single_choice", "multi_choice") and not q.options:
            continue
        out.append(q)
    return out


def _validate_nonempty(questions: list[ExtractedQuestion]) -> list[ExtractedQuestion]:
    out: list[ExtractedQuestion] = []
    for q in questions:
        if not (q.question_text or "").strip():
            continue
        if q.type in ("single_choice", "multi_choice") and not q.options:
            continue
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
