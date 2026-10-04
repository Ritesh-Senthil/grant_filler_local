import re
import logging
from dataclasses import dataclass

from app.models import Fact
from app.services.llm_types import Embedder
from app.services.semantic_facts import cosine_similarity

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


@dataclass
class Evidence:
    fact_id: str
    text: str
    score: float


@dataclass
class EvidenceIndex:
    ids: list[str]
    texts: list[str]
    embeddings: list[list[float]] | None


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


async def build_evidence_index(
    embedder: Embedder,
    facts: list[Fact],
    *,
    grant_chunks: list[str] | None = None,
    grant_chunk_cap: int = DEFAULT_GRANT_CHUNK_CAP,
) -> EvidenceIndex:
    """Build and embed the evidence corpus once for a generation job."""
    org_rows = build_org_corpus(facts)
    grant_rows: list[tuple[str, str]] = []
    if grant_chunks:
        chunks = [c for c in grant_chunks if (c or "").strip()]
        cap = min(grant_chunk_cap if grant_chunk_cap > 0 else DEFAULT_GRANT_CHUNK_CAP, 500)
        if len(chunks) > cap:
            # Sample across the whole application so appendices and later sections are
            # not silently excluded merely because they occur after the cap.
            if cap == 1:
                chunks = [chunks[0]]
            else:
                indices = [round(i * (len(chunks) - 1) / (cap - 1)) for i in range(cap)]
                chunks = [chunks[index] for index in indices]
        grant_rows = build_grant_chunk_corpus(chunks)
    corpus = grant_rows + org_rows
    ids = [row[0] for row in corpus]
    texts = [row[1] for row in corpus]
    embeddings: list[list[float]] | None = None
    if texts:
        try:
            candidate = await embedder.embed_texts(texts)
            if len(candidate) != len(texts):
                raise RuntimeError("Embedding count mismatch for evidence corpus")
            embeddings = candidate
        except Exception as exc:
            # Chat-only operation remains useful when the optional embedding model is absent.
            logger.warning("Evidence embeddings unavailable; using lexical retrieval: %s", exc)
    return EvidenceIndex(ids=ids, texts=texts, embeddings=embeddings)


def _lexical_score(query: str, document: str) -> float:
    q = set(_tokenize(query))
    d = set(_tokenize(document))
    if not q or not d:
        return 0.0
    overlap = len(q & d)
    return overlap / max(1, len(q)) + overlap / max(1, len(d)) * 0.1


async def retrieve_evidence(
    embedder: Embedder,
    question_text: str,
    facts: list[Fact],
    top_k: int = 8,
    *,
    grant_chunks: list[str] | None = None,
    grant_chunk_cap: int = DEFAULT_GRANT_CHUNK_CAP,
    index: EvidenceIndex | None = None,
) -> list[Evidence]:
    """Dense retrieval over saved organization facts, optionally merged with grant source chunks."""
    if index is None:
        index = await build_evidence_index(
            embedder,
            facts,
            grant_chunks=grant_chunks,
            grant_chunk_cap=grant_chunk_cap,
        )
    if not index.texts:
        return []
    docs = index.texts
    ids = index.ids
    q_raw = (question_text or "").strip()
    if not q_raw:
        q_raw = " "
    scored: list[tuple[int, float]]
    if index.embeddings is not None:
        try:
            q_emb = await embedder.embed_text(q_raw)
            scored = [
                (i, cosine_similarity(q_emb, index.embeddings[i])) for i in range(len(docs))
            ]
        except Exception as exc:
            logger.warning("Question embedding unavailable; using lexical retrieval: %s", exc)
            scored = [(i, _lexical_score(q_raw, docs[i])) for i in range(len(docs))]
    else:
        scored = [(i, _lexical_score(q_raw, docs[i])) for i in range(len(docs))]
    scored.sort(key=lambda x: x[1], reverse=True)
    ranked = scored[:top_k]
    return [Evidence(fact_id=ids[i], text=docs[i], score=sc) for i, sc in ranked]
