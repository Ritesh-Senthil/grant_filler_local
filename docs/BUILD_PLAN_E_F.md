# Build plan: E (exports) + F (downloads) — **shipped**

This plan records what was **already in the repo** before the polish pass, what we **finished**, and optional follow-ups. Roadmap: [E. PDF export](../ROADMAP.md#e-pdf-export), [F. File downloads](../ROADMAP.md#f-file-downloads).

---

## Product intent (authoritative)

| Area | Intent |
|------|--------|
| **PDF** | One clean, shareable Q&A document: readable typography, numbered questions, no internal status tags, **“Exported:”** line respects **Settings → Locale** (`iso` / `en-US` / `en-GB`). |
| **DOCX** | Same information architecture as PDF: title, optional org line, export line, per-question headings and **Answer:** blocks; core document metadata (title, subject). |
| **Markdown** | Consistent with PDF/DOCX: title, org line, italic export line, numbered `##` sections. |
| **Branding in body** | If the org has a **header display name** or **legal name**, the first line after the grant title is included in all three formats (not in the download filename). |
| **Filename** | `{SanitizedGrantName}_{YYYY-MM-DD}.pdf|docx|md` (existing behavior; date is export day in UTC for the filename stem). |
| **Download UX** | Browser should **Save / Save As**, not open PDF/MD in a new tab. |

---

## Inventory: what was **already built** (pre-polish)

Verified in code before changes:

- **Backend**
  - `POST /api/v1/grants/{id}/export` with `format`: `qa_pdf` | `markdown` | `docx` — writes to `exports/{grant_id}.{ext}` and returns `file_key`, `download_path`, `filename`.
  - `GET /api/v1/files/{path}` for paths under `exports/`: `Content-Disposition: attachment` with RFC 6266 / `filename*` (UTF-8) via `content_disposition_attachment` + `sanitize_content_disposition_filename` (`download_filename.py`).
  - `build_export_download_filename` for safe, dated basenames.
  - PDF/DOCX/MD builders in `app/services/export.py` with **no** `[needs manual input]` / review flags in customer output (`test_export_content.py`).
- **Frontend**
  - `api.exportGrant` + `downloadExportedFile` in `utils/downloadFile.ts`: `fetch` → `blob` → **temporary** `<a download=…>` — no `target="_blank"` for exports (`downloadFile.test.ts`).

Gaps vs roadmap were mainly **polish** and **locale on the “Exported:” line** (Settings had a locale stub; export used fixed ISO-8601 UTC only).

---

## Shipped in this work

1. **`app/services/export_datetime.py`**  
   - `format_export_timestamp(utc, locale)` for `iso`, `en-US` (12h + AM/PM), `en-GB` (24h), and safe fallback for unknown keys.

2. **`ExportContext`** in `app/services/export.py`  
   - `exported_at_label` (locale-formatted) + optional `organization_line` (from `default-org` **header display name** or **legal name** when set).

3. **Export route** (`main.py`)  
   - Reads `load_locale_override(settings.data_dir) or "iso"`, loads org, passes `ExportContext` into `build_qa_pdf` / `build_qa_docx` / `build_qa_markdown`.

4. **PDF (fpdf2)**  
   - `QAPDF` header title **“Application responses”**, metadata `Title` / `Creator`, grant name in footer with page number, margined body, list-order **1. (type)** blocks, light separator between questions, org + export lines under the grant title.

5. **DOCX (python-docx)**  
   - Calibri 11, 1.5 line spacing default, large bold title, italic org + export lines, `Heading 2` per question, **Answer:** bold + body, `core_properties` title/subject/keywords.

6. **Tests**  
   - `test_export_datetime.py`, extended `test_export_content.py` (context + PDF text via PyMuPDF, DOCX `word/document.xml`).

7. **Roadmap**  
   - Sections E and F marked complete in `ROADMAP.md`.

---

## Optional follow-ups (not required for E + F)

- **Filename + org** — e.g. prefix with a short org slug; keep careful about length and PII.
- **In-app dates** — use the same `format_export_timestamp` helper anywhere UI shows “last exported” (when that surface exists).
- **DOCX** — custom styles in `styles.xml` for a fully branded template (logos are out of scope for v1 export builder).
- **PDF** — non-Latin grant titles: still use `_txt` normalization; consider a Unicode-capable path later if product requires it.

---

## Suggested verification (manual)

1. Set **Settings → Locale** to `en-US` and export PDF — confirm “Exported:” reads with 12h time.  
2. Export **DOCX** and open in Word or Google Docs — check headings, answers, and metadata.  
3. Click **Download** for PDF — file saves; browser does not replace the app with a PDF view (same-origin; `download` attribute used).

---

## Changelog

| Date | Notes |
|------|--------|
| 2026-04-18 | E + F build plan: inventory, shipped scope, follow-ups. |
