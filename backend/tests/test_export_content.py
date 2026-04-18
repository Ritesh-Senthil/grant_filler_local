"""Export builders: no internal status tags in customer-facing files."""

from types import SimpleNamespace

from app.models import Answer, Question
from app.services.export import build_qa_docx, build_qa_markdown, build_qa_pdf


def _grant():
    return SimpleNamespace(name="Test Grant")


def _q():
    return SimpleNamespace(
        question_id="q1",
        question_text="Why?",
        q_type="textarea",
        sort_order=0,
    )


def _answer(**kwargs):
    a = Answer(
        grant_id="g1",
        question_id="q1",
        answer_value="Hello",
        reviewed=True,
        needs_manual_input=True,
        evidence_fact_ids=[],
    )
    for k, v in kwargs.items():
        setattr(a, k, v)
    return a


def test_pdf_excludes_internal_tags():
    g = _grant()
    qs = [_q()]
    ans = [_answer()]
    pdf = build_qa_pdf(g, qs, ans)
    low = pdf.lower()
    assert b"[needs manual input]" not in low
    assert b"[reviewed]" not in low
    assert b"needs manual input" not in low
    assert pdf.startswith(b"%PDF")


def test_markdown_excludes_internal_tags():
    g = _grant()
    qs = [_q()]
    ans = [_answer()]
    md = build_qa_markdown(g, qs, ans).lower()
    assert "needs manual input" not in md
    assert "hello" in md


def test_docx_builds_without_flags():
    g = _grant()
    qs = [_q()]
    ans = [_answer()]
    raw = build_qa_docx(g, qs, ans)
    assert b"needs manual input" not in raw.lower()
    assert b"[reviewed]" not in raw.lower()


def test_question_model_still_works_with_builders():
    """Ensure real Question rows work (integration-style smoke)."""
    g = SimpleNamespace(name="UniqueGrantXYZ")
    q = Question(
        grant_id="g1",
        question_id="q1",
        question_text="T",
        q_type="text",
        sort_order=0,
    )
    pdf = build_qa_pdf(g, [q], [])
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 200
