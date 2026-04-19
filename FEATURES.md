# GrantFiller — Features, architecture, and operations guide

This document is aimed at **nonprofit staff**, **volunteer technologists**, and **evaluators** who want to understand what the application does, how it is built, what it costs to run, and what to expect before relying on it for real grant submissions.

**Important:** GrantFiller assists with drafting; **all outputs require human review** before you submit anything to a funder. The source code is under the **[MIT License](LICENSE)**; see also the [License](README.md#license) section in **README.md** for how that relates to grant submissions.

---

## 1. What GrantFiller is

GrantFiller is a **local-first** web application that helps your team:

1. **Capture** grant application questions from a **PDF**, **Word (.docx)** file, or a **public web page** (URL).
2. **Draft** answers using your **saved organization facts** plus **relevant excerpts** from the application materials.
3. **Review**, reorder, and refine answers in the browser.
4. **Export** a polished **PDF**, **Word (.docx)**, or **Markdown** Q&A document.
5. **Learn** new reusable facts from a completed application into your **organization memory** (optional).

There is **no multi-tenant cloud service** in this repository: you run the API and UI on a machine you control. Data stays under a folder you configure (`DATA_DIR`).

---

## 2. What GrantFiller is not (today)

- **Not** a hosted SaaS with accounts, billing, or shared infrastructure (unless you deploy it that way yourself).
- **Not** a replacement for legal, finance, or compliance review.
- **Not** guaranteed to extract every question from every PDF or portal layout; complex forms, scans, and login-only portals may need manual cleanup.
- **Not** a full grant **management** system (deadlines, assignments across many users, CRM) — it focuses on **one application at a time** as a “workspace” per grant.
- **No login / authentication** in the current codebase: anyone who can reach the app in your network can use the API and UI. Treat network access accordingly.

---

## 3. Feature catalog

### 3.1 Dashboard (`/`)

- **List grants** with name, status, source type, and timestamps.
- **Grant status (`draft` / `ready`)** — shown in the UI as e.g. “Getting started” / “In progress”. The API stores `draft` or `ready`; the backend typically moves a grant to **`ready`** after a **successful parse or generate** job (not something the current UI edits as a separate control—use **PUT `/api/v1/grants/{id}`** with `status` if you need to set it from an integration).
- **Create a new grant** (name; default source type PDF; optional URLs can be set on the grant page).
- **Open** a grant, **delete** a grant (with confirmation).
- **Duplicate grant** — copies uploaded source file and indexed text chunks; can optionally copy **questions and answers** (`include_qa`).
- **AI readiness banner** — warns if Ollama is not reachable or Gemini API key is missing, with links to Settings and provider docs.

### 3.2 Grant workspace (`/grants/:id`)

**Metadata and sources**

- Edit **grant name**, **grant URL**, **portal URL**; persist with explicit **Save** (dirty-state tracking, leave / refresh warnings).
- **Export and some URL actions use saved server state** — the UI asks you to **Save** before **export** (PDF/DOCX/Markdown) and before **Preview** / **Find questions on page** when the draft URL or other fields differ from what was last saved.
- **Upload** application PDF or DOCX (size limit configurable, default **50 MB**).
- **Import from URL** — uses the grant’s URL fields; supports HTTPS fetch, text extraction, optional **linked PDF** discovery, and (when configured) **headless Chromium (Playwright)** for JavaScript-heavy pages.
- **Preview URL** — fetch and show extracted text preview and warnings before running a full parse.

**Question extraction (“Find questions”)**

- Background **parse** job: extracts text (PyMuPDF for PDF, python-docx for DOCX, web pipeline for URLs), chunks text, calls the LLM to produce structured **questions** (with types, options, order).
- **Re-run parse** is guarded when it would **replace** existing questions or non-empty answers (confirmation in UI).

**Answers and review**

- Per-question editors for all supported **question types** (see [§3.5](#35-question-and-answer-types)).
- **Draft with AI** — background **generate** job: retrieval over **org facts** + **grant source chunks**, then LLM batch output with evidence IDs stored on answers where applicable.
- Optional **subset generate** — draft only selected question IDs (API supports `question_ids`).
- Flags: **Reviewed**, **Needs manual input**; marking reviewed **clears** needs-manual-input when successful; **cannot** mark reviewed when the answer is effectively empty (API 422 + UI guard).
- **PATCH answer API** — body supports **`answer_value`** and **`reviewed`** only (`AnswerPatch`). **`needs_manual_input`** is not set by the client PATCH; it is determined by the **generate** job and by **review/empty-answer** rules on the server.
- **Evidence** — answers can store `evidence_fact_ids` linking to facts or synthetic `grant_chunk_*` ids for traceability in the retrieval pipeline.

**Question list UX**

- **Drag-and-drop reorder** (@dnd-kit) with a grip handle and activation distance so scrolling is not confused with dragging.
- **Dynamic numbering** (1., 2., …) from current order; stable DOM ids for deep links from org facts back to a question (`#` fragment).

**Exports**

- **PDF**, **DOCX**, and **Markdown** exports of Q&A (no internal machine type labels like `multi_choice` in customer files).
- **Exported at** line respects **Settings → Locale** (`iso`, `en-US`, `en-GB`).
- Optional **organization line** in exports (header display name or legal name from the default org record).
- Download uses **attachment** disposition and a **safe filename**; the browser uses a blob + **Save** pattern (not “open in new tab” for exports).

**Organization learning**

- **Learn facts from this grant** — background job proposes new **facts** from Q&A; server merges duplicates using **embeddings** and similarity thresholds when enabled.

**Jobs**

- **Poll job status** (`/api/v1/jobs/{id}`) for parse, generate, and learn-org jobs: `pending` → `running` → `completed` / `failed` with progress and error text.

### 3.3 Organization facts (`/org`)

- **CRUD** for organization **facts** (key, value, optional manual source string).
- **Provenance** for facts learned from grants: link back to grant and question (with preview text when available).
- Copy clarifies that **branding and profile-style fields** are edited under **Settings**; this page is **memory / facts**.

### 3.4 Settings (`/settings`)

- **Organization record** — the API exposes **header display name** and **banner** for editing. The database may also store **legal name**, **mission**, **address**, and **extra sections** on the `organizations` row for future or internal use; export branding lines use **header display name** or **legal name** when set. Full profile editing beyond facts is described in roadmap/build plans (`docs/BUILD_PLAN_A_I_L.md`).

- **Header branding** — `header_display_name` and **banner image** upload/remove (JPEG, PNG, WebP, GIF); shown in the app shell.
- **Appearance** — light/dark theme stored in **browser localStorage** (`grantfiller.theme`).
- **LLM provider** — choose **Ollama (local)** or **Gemini (cloud)**; preference can override `.env` and is stored in `DATA_DIR/app_preferences.json` (with reset to env default).
- **Locale (stub)** — persisted for future date formatting across the app; already drives **export timestamp** formatting.
- **Features** — short bullet summary of product capabilities.
- **Enhancement request** — submits text; backend **appends JSON lines** to `DATA_DIR/enhancement_requests.jsonl` (no outbound email in this build).
- **Developer credits** — read-only links from environment variables (`GRANTFILLER_DEV_*`).

### 3.5 Question and answer types

| Internal type   | User-facing idea (UI labels) | Answer storage (summary) |
|----------------|------------------------------|---------------------------|
| `textarea`     | Long answer                  | String |
| `text`         | Short answer                 | String |
| `yes_no`       | Yes / No                     | Normalized `"Yes"` / `"No"` |
| `single_choice`| Pick one                     | One string from `options` |
| `multi_choice` | Pick any that apply          | JSON array of strings from `options` |
| `number`       | Number                       | Number; rejects NaN/Inf |
| `date`         | Date                         | ISO `YYYY-MM-DD` |

Questions may also carry **`required`** and optional **`char_limit`** (enforced in the answer UI for text-like types where implemented).

The model may return **`INSUFFICIENT_INFO`** for text-like answers when evidence is weak; empty answers and that sentinel are treated as **not review-ready**.

### 3.6 Global shell (`App.tsx`)

- Sticky **header** with org banner, **GrantFiller** title, optional org display name.
- Nav: **Grants**, **Your organization**, **Settings** (no theme toggle in the nav — theme lives in Settings).

### 3.7 API surface (machine-readable)

All routes are under **`/api/v1/`** unless you mount the app differently.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/health` | Liveness |
| GET | `/api/v1/config` | LLM provider, **`llm_provider_source`** (env vs user file), **`llm_configured`**, **`chat_model`**, **`embed_model`**, resolved **`data_dir`** |
| PATCH | `/api/v1/llm` | Set user LLM provider preference |
| DELETE | `/api/v1/llm` | Clear user LLM preference (use `.env` again) |
| GET | `/api/v1/org` | Organization read (header + banner key) |
| PUT | `/api/v1/org` | Update header display name |
| POST | `/api/v1/org/banner` | Multipart banner upload |
| DELETE | `/api/v1/org/banner` | Remove banner |
| GET | `/api/v1/app/developer-credits` | Read-only developer links |
| GET/PATCH | `/api/v1/preferences` | Locale stub |
| POST | `/api/v1/enhancements` | Append enhancement request |
| GET/POST/PUT/DELETE | `/api/v1/org/facts` … | Facts CRUD |
| GET/POST | `/api/v1/grants` | List / create grants |
| POST | `/api/v1/grants/{id}/duplicate` | Duplicate grant |
| GET/PUT/DELETE | `/api/v1/grants/{id}` | Grant CRUD |
| POST | `/api/v1/grants/{id}/files` | Upload source file |
| POST | `/api/v1/grants/{id}/parse` | Enqueue parse job |
| POST | `/api/v1/grants/{id}/preview-url` | URL preview |
| POST | `/api/v1/grants/{id}/generate` | Enqueue answer generation |
| POST | `/api/v1/grants/{id}/learn-org` | Enqueue learn-org job |
| POST | `/api/v1/grants/{id}/export` | Build export file |
| PATCH | `/api/v1/grants/{id}/questions/{qid}` | Patch single answer / review flags |
| PUT | `/api/v1/grants/{id}/questions/reorder` | Reorder questions |
| GET | `/api/v1/jobs/{id}` | Job status |
| GET | `/api/v1/files/{path}` | Download stored blobs (exports get attachment filename) |

Interactive API docs: run the backend and open **`/docs`** (Swagger UI).

---

## 4. Architecture (high level)

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (Vite dev server or static build)                   │
│  React 18 + React Router + Tailwind + @dnd-kit               │
│  Proxies /api → FastAPI (see frontend/vite.config.ts)        │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP (local)
┌───────────────────────────▼─────────────────────────────────┐
│  FastAPI (`backend/app/main.py`)                             │
│  Async SQLAlchemy + aiosqlite → SQLite under DATA_DIR        │
│  BackgroundTasks → job_runner (parse / generate / learn)   │
└──────┬───────────────────────────────┬──────────────────────┘
       │                               │
       │ file blobs                      │ LLM + embeddings
       ▼                               ▼
┌──────────────┐                 ┌───────────────────┐
│ Local disk   │                 │ Ollama (default) │
│ DATA_DIR/    │                 │ or Google Gemini │
│ blobs + DB   │                 │ (google-genai)   │
└──────────────┘                 └───────────────────┘
```

**Backend layout (conceptual)**

- **`main.py`** — HTTP routes, CORS, wiring dependencies.
- **`config.py`** — Pydantic settings from `backend/.env` and environment.
- **`database.py`** — Engine, sessions, lightweight SQLite migrations (e.g. new columns).
- **`storage.py`** — Content-addressed files under `DATA_DIR/blobs`.
- **`job_runner.py`** — Long-running parse / generate / learn_org pipelines.
- **`services/`** — Ingest (PDF/DOCX), web fetch + Playwright, question extraction, retrieval, answer generation, export builders, semantic fact merge, etc.
- **`preferences.py`** — JSON file for user overrides (LLM provider, locale).

**Frontend layout (conceptual)**

- **`pages/`** — Dashboard, Grant, Org, Settings.
- **`components/`** — Shared widgets (e.g. `QuestionAnswerField`).
- **`utils/`** — Grant workspace dirty detection, question labels, downloads, theme.

---

## 5. Data storage and backup

| Location | Contents |
|----------|----------|
| `DATA_DIR/grantfiller.db` | SQLite database (grants, questions, answers, jobs, facts, org row) |
| `DATA_DIR/blobs/` | Uploaded PDFs/DOCX, org banners, export artifacts |
| `DATA_DIR/app_preferences.json` | User LLM choice, locale stub |
| `DATA_DIR/enhancement_requests.jsonl` | One JSON object per enhancement submission |

**Backup:** copy the entire `DATA_DIR` folder while the app is idle or after a clean shutdown for consistency.

---

## 6. Dependencies

### 6.1 Runtime — backend (`backend/pyproject.toml`)

| Package | Role |
|---------|------|
| **FastAPI** + **uvicorn** | HTTP API server |
| **SQLAlchemy** (async) + **aiosqlite** | Persistence |
| **Pydantic** / **pydantic-settings** | Schemas and configuration |
| **httpx** | Outbound HTTP (e.g. Ollama, Gemini, web fetch) |
| **python-multipart** | File uploads |
| **PyMuPDF** (`fitz`) | PDF text extraction |
| **python-docx** | DOCX ingest + export |
| **fpdf2** | PDF export |
| **google-genai** | Gemini chat + embeddings when provider is Gemini |
| **trafilatura** | Main HTML article extraction for URLs |
| **certifi** | TLS bundle support |
| **Playwright** | Optional headless browser for difficult URLs (`playwright install chromium`) |

**Dev:** pytest, pytest-asyncio, ruff (optional).

### 6.2 Runtime — frontend (`frontend/package.json`)

| Package | Role |
|---------|------|
| **React** + **react-dom** | UI |
| **react-router-dom** | Routing |
| **@dnd-kit/*** | Accessible drag-and-drop reorder |
| **Vite** + **TypeScript** + **Tailwind** + **PostCSS** | Build and styling |
| **Vitest** + **jsdom** | Unit tests (dev) |

### 6.3 External services (your responsibility)

| Service | When needed |
|---------|-------------|
| **Ollama** | Default path: local chat + embeddings (`OLLAMA_MODEL`, `OLLAMA_EMBED_MODEL`) |
| **Google AI (Gemini)** | If `LLM_PROVIDER=gemini` and `GOOGLE_API_KEY` set |
| **Chromium (Playwright)** | For URL import when static fetch is insufficient |

---

## 7. Cost to run (practical guidance for nonprofits)

Costs depend entirely on **how you deploy** and **which AI path you use**.

### 7.1 Software license

The project is released under the **MIT License** (see **`LICENSE`** in the repo root). Third-party dependencies have their own licenses; confirm with your legal counsel if you redistribute or fork.

### 7.2 Ollama (local, default path)

- **API fees:** typically **$0** for the model inference itself (models run on your hardware).
- **Hardware:** a modern **CPU** can run smaller models slowly; **GPU** (NVIDIA/Apple Silicon) improves speed for 7B–8B-class models. Electricity is the main variable cost.
- **Disk:** models are often **several GB** each (`ollama pull`); embeddings model (e.g. `nomic-embed-text`) adds more.
- **Staff time:** installing Ollama, pulling models, and keeping the machine patched.

### 7.3 Google Gemini (cloud path)

- **API fees:** billed per **Google AI / Gemini** pricing for the configured chat and embedding models (`GEMINI_CHAT_MODEL`, `GEMINI_EMBED_MODEL` in settings). Costs scale with **how often** you parse, generate, and learn facts.
- **No local GPU required** for inference, but you send **application text** and **org facts** to Google’s servers — review your **privacy policy** and any **funder NDAs** before enabling.

### 7.4 Operations

- **Single-machine demo:** negligible beyond electricity.
- **Small org “one volunteer laptop”:** same as above; back up `DATA_DIR`.
- **Hosted server:** add VPS cost ($5–50+/month depending on provider and disk); you still choose Ollama on that box vs Gemini.

---

## 8. Security, privacy, and compliance (non-technical summary)

- **Data residency:** With Ollama, prompts and evidence can stay on your machine **if** you do not use Gemini or external URL fetch beyond what you choose. With Gemini, content is processed by **Google**.
- **URL import:** The server fetches URLs you supply; only use **public** pages you are allowed to scrape; respect funder terms of use.
- **Authentication:** The app does **not** implement user login. Do not expose the API to the public internet without adding **your own** access controls (VPN, reverse proxy auth, firewall rules).
- **HTTPS:** Typical local dev uses HTTP on localhost; production should terminate TLS in front of the app.

---

## 9. Reliability and limitations

- **OCR:** Scanned PDFs without a text layer may extract poorly; prefer text-native PDFs or Word exports from the funder portal.
- **Web portals:** Login walls, CAPTCHAs, and multi-step wizards may not fully load in automated fetch; uploading a **PDF export** of the form is often more reliable.
- **LLM variability:** Wording and completeness change run-to-run; always review.
- **Concurrency:** Parse jobs can run **parallel chunk LLM calls** (bounded by `PARSE_CHUNK_CONCURRENCY`); heavy use can saturate a small Ollama host.

---

## 10. Testing and quality

- **Backend:** `pytest` in `backend/` — API integration, job runner, export content, retrieval, web fetch, settings, coercion, etc. (see `backend/tests/`).
- **Frontend:** `npm test` (Vitest) for theme, downloads, grant workspace, question labels, errors.
- **Local grant URL fixture:** `python3 scripts/serve_grant_web_fixture.py` serves `testdata/grant_web_fixture` at `http://127.0.0.1:8765/` when `WEB_FETCH_ALLOW_HTTP_LOCALHOST=true` in `backend/.env` (see `testdata/grant_web_fixture/README.md`).
- **Synthetic PDF corpus:** `scripts/generate_test_grant_pdfs.py` writes varied **`testdata/grant_pdfs/*.pdf`** for parser/regression testing (not required for normal use).

---

## 11. Related documentation

- **`README.md`** — Quick start, prerequisites, Playwright note, pointer to sample fixtures.
- **`testdata/README.md`** — Sample PDF catalog, HTML URL fixture, suggested parse → generate flow.
- **`.env.example`** — Environment variables with comments.
- **`docs/ROADMAP.md`** — Product roadmap and shipped items.
- **`docs/BUILD_PLAN_E_F.md`** — Export and download design notes.
- **`docs/BUILD_PLAN_A_I_L.md`** — Settings / branding / credits plan.

---

## 12. Getting changes into the product

Enhancement requests from Settings append to `enhancement_requests.jsonl` under `DATA_DIR`. For code contributions or issues, use your team’s Git workflow (e.g. GitHub **`Ritesh-Senthil/grant_filler_local`**).

---

*This file was generated to reflect the codebase structure and behavior; if something drifts, prefer the code and tests as the source of truth and update this document in the same change.*
