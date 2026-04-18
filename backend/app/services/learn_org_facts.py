"""Extract reusable organization facts from grant Q&A for future drafts."""

from pydantic import BaseModel, Field

from app.models import Answer, Question
from app.services.llm_types import LlmClient


class ExtractedOrgFact(BaseModel):
    key: str = Field(..., description="Short label, e.g. 'Service area' or 'Annual budget'")
    value: str = Field(..., description="Concrete fact drawn from the answer")
    source_question_id: str = Field(
        default="",
        description="The question_id from the grant Q&A block this fact is primarily drawn from",
    )


class LearnOrgFactsPayload(BaseModel):
    facts: list[ExtractedOrgFact] = Field(default_factory=list)


SYSTEM = """You help nonprofit staff reuse grant answers as organization facts.

You receive:
- Existing saved facts (key: value) — do not repeat these; only add NEW or materially richer facts.
- Question/answer pairs from one grant application.

Task: Propose up to 12 concise, reusable facts that would help write future grant applications.
Rules:
- Only include facts clearly supported by the answers (no invention).
- Skip vague filler, duplicates of existing facts, or grant-specific deadlines unless they define ongoing policy.
  (The server also merges semantically similar facts via embeddings, so near-duplicate wording is handled automatically.)
- Keys: short noun phrases (2–6 words). Values: one or two sentences max.
- For each fact, set source_question_id to the question_id from the Q&A block below when the fact is mainly grounded in that answer (copy the id exactly from the [question_id: ...] line).
- If nothing new is extractable, return {"facts":[]}.

Return JSON only: {"facts":[{"key":"","value":"","source_question_id":""},...]}"""


def answer_value_text(a: Answer) -> str:
    raw = a.answer_value
    if raw is None or raw == "":
        return ""
    if isinstance(raw, list):
        return ", ".join(str(x) for x in raw)
    return str(raw).strip()


def _answer_text(q: Question, a: Answer) -> str:
    return answer_value_text(a)


def has_any_nonempty_answer(answers: list[Answer]) -> bool:
    return any(answer_value_text(a) for a in answers)


def build_learn_org_user_prompt(
    existing: list[tuple[str, str]],
    pairs: list[tuple[Question, Answer]],
) -> str:
    lines = [
        "Existing saved organization facts:",
    ]
    if not existing:
        lines.append("(none)")
    else:
        for k, v in existing[:80]:
            lines.append(f"- {k}: {v}")
    lines.extend(["", "Grant Q&A (use these to infer new facts):"])
    n = 0
    for q, a in pairs:
        txt = _answer_text(q, a)
        if not txt:
            continue
        lines.append(f"[question_id: {q.question_id}]")
        lines.append(f"Q: {q.question_text}")
        lines.append(f"A: {txt}")
        lines.append("")
        n += 1
    if n == 0:
        lines.append("(no non-empty answers)")
    return "\n".join(lines)


def norm_fact_key(k: str) -> str:
    return " ".join((k or "").lower().split())


def nonempty_qa_pairs(pairs: list[tuple[Question, Answer]]) -> list[tuple[Question, Answer]]:
    return [(q, a) for q, a in pairs if _answer_text(q, a)]


async def extract_new_facts_from_grant(
    llm: LlmClient,
    existing_facts: list,
    pairs: list[tuple[Question, Answer]],
) -> list[ExtractedOrgFact]:
    """Call LLM; return extracted facts (may be empty)."""
    if not nonempty_qa_pairs(pairs):
        return []
    existing_kv = [(f.key or "", f.value or "") for f in existing_facts]
    user = build_learn_org_user_prompt(existing_kv, pairs)
    payload = await llm.chat_json(SYSTEM, user, LearnOrgFactsPayload)
    return list(payload.facts or [])
