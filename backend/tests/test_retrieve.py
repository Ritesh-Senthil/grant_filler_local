"""Evidence retrieval edge cases."""

from app.models import Fact, Organization
from app.services.retrieve import retrieve_evidence


def test_retrieve_empty_question_tokens():
    org = Organization(id="default-org", legal_name="X")
    facts: list[Fact] = []
    ev = retrieve_evidence("???", org, facts, top_k=5)
    assert isinstance(ev, list)


def test_retrieve_returns_profile_rows():
    org = Organization(
        id="default-org",
        legal_name="Acme Nonprofit",
        mission_short="We teach kids.",
        mission_long="",
        address="123 St",
    )
    facts = [Fact(id="f1", org_id="default-org", key="Founded", value="1999", source="")]
    ev = retrieve_evidence("What is your legal name and mission?", org, facts, top_k=5)
    texts = " ".join(e.text for e in ev)
    assert "Acme" in texts or "teach" in texts or "1999" in texts
