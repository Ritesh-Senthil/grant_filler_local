import fitz
from docx import Document
from io import BytesIO

from app.config import Settings
from app.services.ingest import extract_docx_bytes, extract_pdf_bytes, segments_to_chunks


def _pdf_with_text(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    buf = doc.tobytes()
    doc.close()
    return buf


def test_extract_pdf_roundtrip():
    data = _pdf_with_text("Application Question 1: What is your mission?")
    segs = extract_pdf_bytes(data)
    assert len(segs) >= 1
    assert "mission" in segs[0].text.lower()


def test_extract_pdf_empty_pages():
    doc = fitz.open()
    doc.new_page()
    buf = doc.tobytes()
    doc.close()
    segs = extract_pdf_bytes(buf)
    assert segs == []


def test_extract_docx_roundtrip():
    buf = BytesIO()
    d = Document()
    d.add_paragraph("Grant question: Annual budget?")
    d.save(buf)
    segs = extract_docx_bytes(buf.getvalue())
    assert len(segs) == 1
    assert "budget" in segs[0].text.lower()


def test_segments_to_chunks_single():
    from app.services.ingest import TextSegment

    s = [TextSegment(label="p1", text="x" * 100)]
    chunks = segments_to_chunks(s, Settings())
    assert len(chunks) == 1


def test_segments_to_chunks_splits_long():
    from app.services.ingest import CHUNK_MAX_CHARS, TextSegment

    long_text = "word " * (CHUNK_MAX_CHARS // 5 + 50)
    s = [TextSegment(label="p1", text=long_text)]
    chunks = segments_to_chunks(s, Settings())
    assert len(chunks) >= 2
