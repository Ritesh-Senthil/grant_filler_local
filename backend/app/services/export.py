from datetime import datetime
from io import BytesIO

from docx import Document
from fpdf import FPDF

from app.models import Answer, Grant, Question


def _txt(s: str) -> str:
    """fpdf2 core fonts are latin-1; normalize for safety."""
    if not s:
        return ""
    return s.encode("latin-1", errors="replace").decode("latin-1")


class QAPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, _txt("Grant application — Q&A export"), ln=True)
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def build_qa_pdf(grant: Grant, questions: list[Question], answers: list[Answer]) -> bytes:
    answer_map = {a.question_id: a for a in answers}
    pdf = QAPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, _txt(f"Grant: {grant.name}"), ln=True)
    pdf.multi_cell(0, 6, _txt(f"Exported: {datetime.utcnow().isoformat()}Z"), ln=True)
    pdf.ln(4)
    for q in sorted(questions, key=lambda x: x.sort_order):
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(0, 6, _txt(f"Q ({q.q_type}): {q.question_text}"), ln=True)
        pdf.set_font("Helvetica", "", 10)
        a = answer_map.get(q.question_id)
        val = ""
        if a and a.answer_value is not None:
            if isinstance(a.answer_value, list):
                val = ", ".join(str(x) for x in a.answer_value)
            else:
                val = str(a.answer_value)
        else:
            val = "(no answer yet)"
        flag = ""
        if a and a.needs_manual_input:
            flag = " [needs manual input]"
        if a and a.reviewed:
            flag += " [reviewed]"
        pdf.multi_cell(0, 6, _txt(f"A: {val}{flag}"), ln=True)
        pdf.ln(3)
    out = BytesIO()
    pdf.output(out)
    return out.getvalue()


def build_qa_markdown(grant: Grant, questions: list[Question], answers: list[Answer]) -> str:
    answer_map = {a.question_id: a for a in answers}
    lines = [
        f"# {grant.name}",
        "",
        f"_Exported {datetime.utcnow().isoformat()}Z_",
        "",
    ]
    for q in sorted(questions, key=lambda x: x.sort_order):
        lines.append(f"## Q ({q.q_type})")
        lines.append("")
        lines.append(q.question_text)
        lines.append("")
        a = answer_map.get(q.question_id)
        val = ""
        if a and a.answer_value is not None:
            if isinstance(a.answer_value, list):
                val = ", ".join(str(x) for x in a.answer_value)
            else:
                val = str(a.answer_value)
        lines.append(f"**Answer:** {val or '(no answer yet)'}")
        if a and a.needs_manual_input:
            lines.append("_Needs manual input_")
        lines.append("")
    return "\n".join(lines)


def build_qa_docx(grant: Grant, questions: list[Question], answers: list[Answer]) -> bytes:
    """Word-compatible .docx for Q&A (opens in Word, Google Docs, etc.)."""
    answer_map = {a.question_id: a for a in answers}
    doc = Document()
    doc.add_heading(grant.name, 0)
    doc.add_paragraph(f"Exported {datetime.utcnow().isoformat()}Z")
    for q in sorted(questions, key=lambda x: x.sort_order):
        doc.add_heading(f"Question ({q.q_type})", level=2)
        doc.add_paragraph(q.question_text)
        a = answer_map.get(q.question_id)
        val = ""
        if a and a.answer_value is not None:
            if isinstance(a.answer_value, list):
                val = ", ".join(str(x) for x in a.answer_value)
            else:
                val = str(a.answer_value)
        else:
            val = "(no answer yet)"
        flags = []
        if a and a.needs_manual_input:
            flags.append("needs manual input")
        if a and a.reviewed:
            flags.append("reviewed")
        suffix = f" ({', '.join(flags)})" if flags else ""
        doc.add_paragraph(f"Answer: {val}{suffix}")
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()
