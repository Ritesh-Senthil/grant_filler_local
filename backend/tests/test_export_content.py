"""Export builders: no internal status tags in customer-facing files."""

import io
import zipfile
from types import SimpleNamespace

import fitz  # pymupdf

from app.models import Answer, Question
from app.services.export import ExportContext, build_qa_docx, build_qa_markdown, build_qa_pdf


def _grant():
    return SimpleNamespace(name="Test Grant")


def _q(**kwargs):
    d = {
        "question_id": "q1",
        "question_text": "Why?",
        "q_type": "textarea",
        "sort_order": 0,
    }
    d.update(kwargs)
    return SimpleNamespace(**d)


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
    qs = [_q(q_type="integer")]
    ans = [_answer()]
    pdf = build_qa_pdf(g, qs, ans)
    low = pdf.lower()
    assert b"[needs manual input]" not in low
    assert b"[reviewed]" not in low
    assert b"needs manual input" not in low
    assert b"integer" not in low
    assert pdf.startswith(b"%PDF")
    doc = fitz.open(stream=pdf, filetype="pdf")
    text = "".join(p.get_text() for p in doc).lower()
    assert "integer" not in text


def test_markdown_excludes_internal_tags():
    g = _grant()
    qs = [_q()]
    ans = [_answer()]
    md = build_qa_markdown(g, qs, ans).lower()
    assert "needs manual input" not in md
    assert "hello" in md
    assert "textarea" not in md
    assert "multiple_choice" not in md


def test_docx_builds_without_flags():
    g = _grant()
    q = _q(q_type="multiple_choice")
    qs = [q]
    ans = [_answer()]
    raw = build_qa_docx(g, qs, ans)
    assert b"needs manual input" not in raw.lower()
    assert b"[reviewed]" not in raw.lower()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        body = zf.read("word/document.xml").decode("utf-8", errors="replace")
    assert "multiple_choice" not in body
    assert "Question 1" in body


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


def test_export_context_appears_in_outputs():
    """Branding and fixed timestamp are embedded (locale/pref wiring tested in main)."""
    g = _grant()
    ctx = ExportContext(exported_at_label="Exported: 2019-06-01 12:00:00 UTC", organization_line="Acme NPO")
    pdf = build_qa_pdf(g, [_q()], [_answer()], ctx)
    doc = fitz.open(stream=pdf, filetype="pdf")
    pdf_text = "".join(p.get_text() for p in doc)
    assert "2019" in pdf_text
    assert "Acme" in pdf_text
    md = build_qa_markdown(g, [_q()], [_answer()], ctx)
    assert "Acme" in md
    assert "2019" in md
    docx = build_qa_docx(g, [_q()], [_answer()], ctx)
    with zipfile.ZipFile(io.BytesIO(docx)) as zf:
        body = zf.read("word/document.xml").decode("utf-8", errors="replace")
    assert "Acme" in body
    assert "2019" in body
