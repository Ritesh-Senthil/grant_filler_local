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
            if text.strip():
                segments.append(TextSegment(label=f"page_{i+1}", text=text.strip()))
    finally:
        doc.close()
    return segments


def extract_docx_bytes(data: bytes) -> list[TextSegment]:
    from io import BytesIO

    doc = Document(BytesIO(data))
    parts: list[str] = []
    for p in doc.paragraphs:
        t = (p.text or "").strip()
        if t:
            parts.append(t)
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
