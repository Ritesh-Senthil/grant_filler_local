"""Evidence retrieval edge cases."""

import re

import pytest

from app.models import Fact
from app.services.retrieve import retrieve_evidence


def _bow_vec(text: str, dim: int = 128) -> list[float]:
    words = re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
    v = [0.0] * dim
    for w in words:
        v[hash(w) % dim] += 1.0
    norm = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / norm for x in v]


class FakeEmbedder:
    async def embed_text(self, text: str) -> list[float]:
        return _bow_vec(text)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed_text(t) for t in texts]


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


async def test_retrieve_empty_question_tokens(fake_embedder: FakeEmbedder):
    facts: list[Fact] = []
    ev = await retrieve_evidence(fake_embedder, "???", facts, top_k=5)
    assert isinstance(ev, list)


async def test_retrieve_includes_grant_chunks(fake_embedder: FakeEmbedder):
    facts: list[Fact] = []
    chunks = [
        "Applicants must describe their annual budget in detail.",
        "Unrelated boilerplate about parking.",
    ]
    ev = await retrieve_evidence(
        fake_embedder,
        "What is the budget requirement?",
        facts,
        top_k=6,
        grant_chunks=chunks,
    )
    joined = " ".join(e.text for e in ev)
    assert "budget" in joined.lower()


async def test_retrieve_returns_fact_rows(fake_embedder: FakeEmbedder):
    facts = [
        Fact(id="f1", org_id="default-org", key="Legal name", value="Acme Nonprofit", source=""),
        Fact(id="f2", org_id="default-org", key="Mission (short)", value="We teach kids.", source=""),
    ]
    ev = await retrieve_evidence(
        fake_embedder, "What is your legal name and mission?", facts, top_k=5
    )
    texts = " ".join(e.text for e in ev)
    assert "Acme" in texts or "teach" in texts
