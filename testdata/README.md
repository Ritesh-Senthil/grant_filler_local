# Test fixtures: sample grants (PDF, web)

Use these assets to **learn GrantFiller end-to-end** without a real funder form: upload or fetch a sample, run **Find questions**, add **organization facts**, run **Draft with AI**, then **export** PDF/DOCX/Markdown.

The [root README](../README.md) only points here so the main install guide stays short; **this file** is the catalog of formats and suggested flows.

---

## Suggested first-time flow (any fixture)

1. Start the **API**, **UI**, and your **LLM** (Ollama or Gemini) as in the main README.
2. **Dashboard** → create a grant → open it.
3. **Application source**
   - **PDF:** upload a file from `grant_pdfs/` (below), then **Find questions in file**.
   - **Web:** follow [Sample HTML page (URL)](#sample-html-page-url).
4. **Your organization** → add a few **facts** (mission, service area, budget band—anything the questions might ask about).
5. Back on the grant → **Draft with AI** (or select questions if your UI supports subset runs).
6. Edit answers, toggle **Reviewed** where appropriate → **Export** PDF or Word.

Expect **variability**: question extraction and drafting depend on the model and layout. The numbered PDFs progress from “easiest” to “stress” layouts.

---

## Sample PDFs (`grant_pdfs/`)

These are committed in the repo (and can be regenerated—see [Regenerating PDFs](#regenerating-pdfs)).

| File | What it simulates | Good for |
|------|-------------------|----------|
| `01_test_grant_clean_linear.pdf` | Single column, clear numbering, mixed short/long and Yes/No / multiple choice–style prompts | **Start here** — easiest text extraction. |
| `02_test_grant_mixed_markers_multipage.pdf` | Sections, bullets, underscores, **multiple pages**, continuation headers | Multipage chunking and section boundaries. |
| `03_test_grant_sparse_whitespace.pdf` | Large vertical gaps, short lines, checkbox-style tiers | Sparse layout / chunk boundaries. |
| `04_test_grant_nested_numbering.pdf` | Sub-items **2(a)**, **2(b)**, grids of checkboxes | How the LLM groups nested items into questions. |
| `05_test_grant_table_like.pdf` | Label + response rows (table-like worksheet) | Row-style “form” PDFs. |
| `06_test_grant_two_column.pdf` | **Two columns** on one page | Reading order vs. visual order (extraction order may differ). |
| `07_test_grant_dense_single_page.pdf` | Dense, small type, repeated checklist block | Stress test for very long single-page text. |

---

## Sample HTML page (URL)

Static **HTML** grant page (not served by the Vite app):

- **Files:** `grant_web_fixture/index.html`
- **Preview:** open the file in your browser (File → Open).
- **Parse via GrantFiller:** serve it over HTTP and allow local fetch in the API:

  ```bash
  # From repo root
  python3 scripts/serve_grant_web_fixture.py
  ```

  Set `WEB_FETCH_ALLOW_HTTP_LOCALHOST=true` in `backend/.env`, restart the API, then set the grant URL to **`http://127.0.0.1:8765/`** (default port).

Full steps: **[grant_web_fixture/README.md](grant_web_fixture/README.md)**.

---

## Regenerating PDFs

From the repo, with `pymupdf` and `fpdf2` available (same stack as the backend; see script header):

```bash
cd backend && .venv/bin/python ../scripts/generate_test_grant_pdfs.py
```

Output: `testdata/grant_pdfs/*.pdf`

---

## See also

- **[FEATURES.md](../FEATURES.md)** — full product behavior, API, limits.
- **Root [README.md](../README.md)** — install and optional pointer to this folder.
