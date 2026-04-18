#!/usr/bin/env python3
"""Generate sample grant-application PDFs for manual testing of parse / question extraction.

Run with pymupdf + fpdf2 on PYTHONPATH (same versions as backend/pyproject.toml), e.g.:

  cd backend && uv run python ../scripts/generate_test_grant_pdfs.py

or, using a local venv:

  cd backend && python3 -m venv .venv && .venv/bin/pip install pymupdf fpdf2
  .venv/bin/python ../scripts/generate_test_grant_pdfs.py

Output: ../testdata/grant_pdfs/*.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

import fitz  # pymupdf
from fpdf import FPDF
from fpdf.enums import XPos, YPos

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "testdata" / "grant_pdfs"


def _txt(s: str) -> str:
    if not s:
        return ""
    return s.encode("latin-1", errors="replace").decode("latin-1")


class GrantPDF(FPDF):
    def __init__(self) -> None:
        super().__init__()
        self.set_auto_page_break(auto=True, margin=18)

    def header(self) -> None:
        self.set_font("Helvetica", "I", 9)
        self.cell(
            0,
            8,
            _txt("Sample grant application (test fixture)"),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            align="R",
        )
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def write_clean_linear() -> Path:
    """Single column, clear numbering — easiest case for text extraction."""
    pdf = GrantPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 8, _txt("Community Impact Mini-Grant — Application"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(2)
    body = """
Instructions: Answer each question below. Items marked (Required) must be completed.

1. Legal name of applicant organization. (Required)
   [Short answer, max 120 characters]

2. Provide a brief mission statement for your organization (2-3 sentences).
   [Long text / narrative]

3. Is your organization registered as a 501(c)(3) nonprofit?
   Yes / No

4. Which primary program area best describes this proposal? (select one)
   A) Education
   B) Health and wellness
   C) Environment and sustainability
   D) Arts and culture

5. Which populations will you serve? (select all that apply)
   - Youth (under 18)
   - Older adults (65+)
   - Low-income households
   - Rural communities

6. Proposed project start date (MM/DD/YYYY):

7. Total amount requested (USD, numbers only):

8. Estimated number of people served annually (integer):

9. Upload is not tested here; describe in one sentence how you will measure outcomes.
   [Other / free text]

10. Certification: I confirm the information is accurate to the best of my knowledge.
    Yes / No
""".strip()
    pdf.multi_cell(0, 6, _txt(body), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    path = OUT_DIR / "01_test_grant_clean_linear.pdf"
    pdf.output(path)
    return path


def write_mixed_markers_multipage() -> Path:
    """Bullets, section headers, continuation across pages, inline limits."""
    pdf = GrantPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 13)
    pdf.multi_cell(0, 7, _txt("Regional Arts Council — FY2026 Project Grant"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(1)
    p1 = """
SECTION I — APPLICANT PROFILE

• Lead artist or collective name:
• Primary contact email:
• Phone (include country code if outside US):

SECTION II — PROJECT NARRATIVE (max 250 words)

Describe the creative work, community need, and how residents will participate.
Use the space below.

________________________________________________________________________________
________________________________________________________________________________

SECTION III — BUDGET SUMMARY

Line item: Artist fees — amount (USD): ____________
Line item: Materials — amount (USD): ____________
Line item: Venue or space — amount (USD): ____________

Total project budget (USD, numeric): ____________

SECTION IV — COMPLIANCE

Circle one: Has this project received funding from this council before?  YES   NO

If you need accessibility accommodations to complete this application, explain here:
""".strip()
    pdf.multi_cell(0, 5.5, _txt(p1), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(
        0,
        7,
        _txt("SECTION V — EVALUATION (continued from previous page)"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.set_font("Helvetica", "", 10)
    p2 = """
How will you know the project succeeded? List up to three measurable indicators.

1)
2)
3)

Risk factors: What could prevent delivery, and how will you mitigate? (paragraph)

Date you expect final reporting to be submitted (YYYY-MM-DD):

Optional: share any links to supporting work (comma-separated URLs, plain text):
""".strip()
    pdf.multi_cell(0, 5.5, _txt(p2), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    path = OUT_DIR / "02_test_grant_mixed_markers_multipage.pdf"
    pdf.output(path)
    return path


def write_sparse_whitespace() -> Path:
    """Lots of vertical space and short lines — tests chunking / sparse pages."""
    pdf = GrantPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, _txt("Micro-grant — Quick Application"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(20)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 8, _txt("Organization legal name:\n\n\n"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(15)
    pdf.multi_cell(
        0,
        8,
        _txt("One-sentence project summary (max 280 characters):\n\n\n"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(15)
    pdf.multi_cell(
        0,
        8,
        _txt(
            "Funding tier requested:\n"
            "  ( ) $2,500   ( ) $5,000   ( ) $10,000\n\n\n"
        ),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(10)
    pdf.multi_cell(0, 8, _txt("Today's date (DD-Mon-YYYY):\n\n"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    path = OUT_DIR / "03_test_grant_sparse_whitespace.pdf"
    pdf.output(path)
    return path


def write_nested_numbering() -> Path:
    """Sub-items like 2(a), 2(b) — exercises LLM grouping."""
    pdf = GrantPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(0, 7, _txt("State STEM Education Grant — Part B"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    text = """
1. District or LEA name:

2. For the lead applicant:
   (a) Title and role:
   (b) Work email:
   (c) Direct phone:

3. Student demographics — approximate headcount (numbers only):
   (a) Grades K-5:
   (b) Grades 6-8:
   (c) Grades 9-12:

4. Will equipment purchased with these funds remain school property?
    Yes / No

5. Select the instructional model (choose one):
    In-person only | Hybrid | Fully virtual

6. Acknowledgements (check all that apply):
    [ ] We have board approval
    [ ] We have a technology use policy
    [ ] We will provide substitute coverage during PD days
""".strip()
    pdf.multi_cell(0, 5.5, _txt(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    path = OUT_DIR / "04_test_grant_nested_numbering.pdf"
    pdf.output(path)
    return path


def write_table_like_mupdf() -> Path:
    """Label/response rows via text boxes — mimics many PDF forms."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    font = "helv"
    size = 10
    y = 72
    page.insert_text((50, 56), "Table-style grant worksheet (test fixture)", fontsize=12, fontname=font)
    rows = [
        ("Applicant / PI name", "_______________________________________________"),
        ("Department or unit", "_______________________________________________"),
        ("Project title (short)", "_______________________________________________"),
        ("IRB or ethics approval status", "Pending | Approved | Not applicable (explain)"),
        ("Anticipated enrollment (N)", "________________"),
        ("Study start date", "____ / ____ / ______"),
        ("Will data be shared publicly?", "Yes | No"),
        (
            "Primary outcome measure",
            "Single choice: survey | observation | administrative data | other: ________",
        ),
    ]
    for label, placeholder in rows:
        page.insert_text((50, y), label + ":", fontsize=size, fontname=font)
        y += 14
        page.insert_text((70, y), placeholder, fontsize=size - 1, fontname="helv", color=(0.25, 0.25, 0.25))
        y += 28
    path = OUT_DIR / "05_test_grant_table_like.pdf"
    doc.save(path)
    doc.close()
    return path


def write_two_column_mupdf() -> Path:
    """Two physical columns — extraction order may differ from visual reading order."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 48), "Two-column layout (test fixture)", fontsize=12, fontname="helv")
    left = """LEFT COLUMN QUESTIONS

1. City where project will run:

2. Primary language of services:
   English | Spanish | Bilingual | Other

3. Number of partner organizations (integer):"""

    right = """RIGHT COLUMN QUESTIONS

4. Fiscal sponsor EIN (if applicable):

5. Award payment preference:
   ACH | Check | Wire

6. Confirm you read the terms: Yes / No"""

    r1 = fitz.Rect(40, 70, 290, 760)
    r2 = fitz.Rect(310, 70, 572, 760)
    page.insert_textbox(r1, left, fontsize=10, fontname="helv", align=fitz.TEXT_ALIGN_LEFT)
    page.insert_textbox(r2, right, fontsize=10, fontname="helv", align=fitz.TEXT_ALIGN_LEFT)
    path = OUT_DIR / "06_test_grant_two_column.pdf"
    doc.save(path)
    doc.close()
    return path


def write_overlapping_small_font_mupdf() -> Path:
    """Dense block, smaller type — stress test for chunk boundaries."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    block = (
        "CAPACITY BUILDING CHECKLIST (dense). "
        "Q1 Staff FTE dedicated to grant (number): ______. "
        "Q2 Years operating (number): ______. "
        "Q3 Mission fit — pick one: Advocacy | Service delivery | Research | Coalition. "
        "Q4 Counties served (multi): North | South | East | West. "
        "Q5 Conflict of interest attestation Yes/No. "
        "Q6 Narrative: describe collaboration in <= 500 characters (short paragraph). "
        "Q7 Reporting due date (ISO date preferred). "
        "Q8 Budget narrative file name (text). "
    ) * 3
    page.insert_textbox(fitz.Rect(36, 48, 576, 756), block, fontsize=7.5, fontname="helv")
    path = OUT_DIR / "07_test_grant_dense_single_page.pdf"
    doc.save(path)
    doc.close()
    return path


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    writers = [
        write_clean_linear,
        write_mixed_markers_multipage,
        write_sparse_whitespace,
        write_nested_numbering,
        write_table_like_mupdf,
        write_two_column_mupdf,
        write_overlapping_small_font_mupdf,
    ]
    paths: list[Path] = []
    for fn in writers:
        paths.append(fn())
    print(f"Wrote {len(paths)} PDFs to {OUT_DIR}:")
    for p in sorted(paths, key=lambda x: x.name):
        print(f"  - {p.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
