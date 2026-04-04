import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.models import Fact, Organization


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


@dataclass
class Evidence:
    fact_id: str
    text: str
    score: float


def build_org_corpus(org: Organization, facts: list[Fact]) -> list[tuple[str, str]]:
    """Return list of (id, text) for retrieval."""
    rows: list[tuple[str, str]] = []
    rows.append(("profile_legal_name", f"legal_name: {org.legal_name}"))
    rows.append(("profile_mission_short", f"mission_short: {org.mission_short}"))
    rows.append(("profile_mission_long", f"mission_long: {org.mission_long}"))
    rows.append(("profile_address", f"address: {org.address}"))
    for sec in org.extra_sections or []:
        if isinstance(sec, dict):
            t = sec.get("title", "")
            c = sec.get("content", "")
            rows.append((f"section_{sec.get('id', 'x')}", f"{t}\n{c}"))
    for f in facts:
        rows.append((f.id, f"{f.key}: {f.value}" + (f" (source: {f.source})" if f.source else "")))
    return rows


def retrieve_evidence(
    question_text: str,
    org: Organization,
    facts: list[Fact],
    top_k: int = 8,
) -> list[Evidence]:
    corpus = build_org_corpus(org, facts)
    if not corpus:
        return []
    docs = [c[1] for c in corpus]
    ids = [c[0] for c in corpus]
    tokenized = [_tokenize(d) for d in docs]
    if not any(tokenized):
        return []
    bm25 = BM25Okapi(tokenized)
    q = _tokenize(question_text)
    if not q:
        return [
            Evidence(fact_id=ids[i], text=docs[i], score=1.0 - i * 0.01) for i in range(min(top_k, len(ids)))
        ]
    scores = bm25.get_scores(q)
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
    return [Evidence(fact_id=ids[idx], text=docs[idx], score=float(sc)) for idx, sc in ranked]
