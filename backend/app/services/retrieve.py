import re
from dataclasses import dataclass

from app.models import Fact
from app.services.llm_types import Embedder
from app.services.semantic_facts import cosine_similarity


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


@dataclass
class Evidence:
    fact_id: str
    text: str
    score: float


# Cap how many grant text chunks enter retrieval (embedding cost + noise).
DEFAULT_GRANT_CHUNK_CAP = 96


def build_org_corpus(facts: list[Fact]) -> list[tuple[str, str]]:
    """Return list of (id, text) for retrieval — organization knowledge comes from facts only."""
    rows: list[tuple[str, str]] = []
    for f in facts:
        rows.append((f.id, f"{f.key}: {f.value}" + (f" (source: {f.source})" if f.source else "")))
    return rows


def build_grant_chunk_corpus(chunks: list[str]) -> list[tuple[str, str]]:
    """Ids like grant_chunk_0 — referenced in evidence_fact_ids for UI/debug."""
    rows: list[tuple[str, str]] = []
    for i, c in enumerate(chunks):
        t = (c or "").strip()
        if not t:
            continue
        rows.append((f"grant_chunk_{i}", f"[Application source — chunk {i + 1}]\n{t}"))
    return rows


async def retrieve_evidence(
    embedder: Embedder,
    question_text: str,
    facts: list[Fact],
    top_k: int = 8,
    *,
    grant_chunks: list[str] | None = None,
    grant_chunk_cap: int = DEFAULT_GRANT_CHUNK_CAP,
) -> list[Evidence]:
    """Dense retrieval over saved organization facts, optionally merged with grant source chunks."""
    org_rows = build_org_corpus(facts)
    grant_rows: list[tuple[str, str]] = []
    if grant_chunks:
        gc = [c for c in grant_chunks if (c or "").strip()]
        cap = grant_chunk_cap if grant_chunk_cap > 0 else DEFAULT_GRANT_CHUNK_CAP
        cap = min(cap, 500)
        if len(gc) > cap:
            gc = gc[:cap]
        grant_rows = build_grant_chunk_corpus(gc)
    corpus = grant_rows + org_rows
    if not corpus:
        return []
    docs = [c[1] for c in corpus]
    ids = [c[0] for c in corpus]
    q_raw = (question_text or "").strip()
    if not q_raw:
        q_raw = " "
    q_emb = await embedder.embed_text(q_raw)
    doc_embs = await embedder.embed_texts(docs)
    if len(doc_embs) != len(docs):
        raise RuntimeError("Embedding count mismatch for evidence corpus")
    if not any(q_emb) and not _tokenize(q_raw):
        return [
            Evidence(fact_id=ids[i], text=docs[i], score=1.0 - i * 0.01) for i in range(min(top_k, len(ids)))
        ]
    scored: list[tuple[int, float]] = []
    for i in range(len(docs)):
        scored.append((i, cosine_similarity(q_emb, doc_embs[i])))
    scored.sort(key=lambda x: x[1], reverse=True)
    ranked = scored[:top_k]
    return [Evidence(fact_id=ids[i], text=docs[i], score=sc) for i, sc in ranked]
