from dataclasses import dataclass

import fitz  # pymupdf
from docx import Document

from app.config import Settings

# Defaults when Settings is not passed (tests).
CHUNK_MAX_CHARS = 32000
CHUNK_OVERLAP = 400


@dataclass
class TextSegment:
    label: str
    text: str


def extract_pdf_bytes(data: bytes) -> list[TextSegment]:
    doc = fitz.open(stream=data, filetype="pdf")
    segments: list[TextSegment] = []
    try:
        for i in range(len(doc)):
            page = doc.load_page(i)
            text = page.get_text("text") or ""
            if not text.strip():
                try:
                    # PyMuPDF uses Tesseract when available. This is best-effort so a
                    # machine without OCR support still returns a clear no-text error.
                    text_page = page.get_textpage_ocr(dpi=150, full=True)
                    text = page.get_text("text", textpage=text_page) or ""
                except Exception:
                    text = ""
            if text.strip():
                segments.append(TextSegment(label=f"page_{i+1}", text=text.strip()))
    finally:
        doc.close()
    return segments


def extract_docx_bytes(data: bytes) -> list[TextSegment]:
    from io import BytesIO

    doc = Document(BytesIO(data))
    parts: list[str] = []

    def add_paragraphs(paragraphs) -> None:
        for paragraph in paragraphs:
            text = (paragraph.text or "").strip()
            if text:
                parts.append(text)

    def add_table(table) -> None:
        for row in table.rows:
            cells: list[str] = []
            for cell in row.cells:
                cell_parts = [(p.text or "").strip() for p in cell.paragraphs]
                cell_text = "\n".join(p for p in cell_parts if p)
                if cell_text:
                    cells.append(cell_text)
                for nested in cell.tables:
                    add_table(nested)
            if cells:
                parts.append(" | ".join(cells))

    # python-docx exposes body paragraphs and tables separately. Reading both is more
    # important than exact interleaving because grant forms commonly put every prompt in a table.
    add_paragraphs(doc.paragraphs)
    for table in doc.tables:
        add_table(table)
    for section in doc.sections:
        add_paragraphs(section.header.paragraphs)
        add_paragraphs(section.footer.paragraphs)
    full = "\n\n".join(parts)
    if not full.strip():
        return []
    return [TextSegment(label="docx_body", text=full)]


def segments_to_chunks(segments: list[TextSegment], settings: Settings | None = None) -> list[str]:
    max_chars = settings.chunk_max_chars if settings else CHUNK_MAX_CHARS
    overlap = settings.chunk_overlap if settings else CHUNK_OVERLAP
    combined = "\n\n".join(f"[{s.label}]\n{s.text}" for s in segments)
    if len(combined) <= max_chars:
        return [combined]
    chunks: list[str] = []
    start = 0
    while start < len(combined):
        end = min(start + max_chars, len(combined))
        chunk = combined[start:end]
        chunks.append(chunk)
        if end >= len(combined):
            break
        start = end - overlap
        if start < 0:
            start = 0
    return chunks
