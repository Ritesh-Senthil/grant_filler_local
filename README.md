# GrantFiller

**Local-first grant application assistant** — ingest a funder’s PDF, Word file, or public web page; extract questions; draft answers from your **organization facts** and the **application text**; review and export polished **PDF**, **Word**, or **Markdown**.

> **Disclaimer:** GrantFiller produces drafts. **Always review** outputs before submitting to any funder. Licensed under the [MIT License](LICENSE).

---

## Table of contents

- [What it does](#what-it-does)
- [How it works (architecture)](#how-it-works-architecture)
- [Clone and install](#clone-and-install)
- [Run the application](#run-the-application)
- [Configure the AI backend](#configure-the-ai-backend)
- [Optional: sample fixtures (PDFs & test website)](#optional-sample-fixtures-pdfs--test-website)
- [Where your data lives](#where-your-data-lives)
- [API reference](#api-reference)
- [Tests](#tests)
- [Repository layout](#repository-layout)
- [Security note](#security-note)
- [License](#license)

---

## What it does

| Area | Capabilities |
|------|----------------|
| **Ingest** | Upload **PDF** or **DOCX**; or point at a **public HTTPS URL** (and optionally **http://127.0.0.1** for local test pages). JS-heavy pages can use **Playwright** (Chromium) after a static fetch. |
| **Questions** | Background **parse** job: text extraction, chunking, **LLM**-assisted structured questions (types, options, order). **Drag-and-drop** reorder; numbering follows list order. |
| **Answers** | **AI draft** uses **retrieval** over org **facts** + indexed **grant source chunks**, then an LLM batch. **Review** / **needs manual input** flags; exports omit internal jargon. |
| **Organization memory** | **Facts** CRUD on `/org`; optional **learn from grant** job proposes new facts with embedding-based deduplication. |
| **Settings** | **Header name & banner**, **theme**, **LLM provider** (Ollama vs Gemini), **locale** (affects export timestamps), enhancement requests (local file append). |
| **Export** | **PDF**, **DOCX**, **Markdown** with professional wording; safe download filenames. |

For a **full feature list** and operations detail, see **[FEATURES.md](FEATURES.md)**.

---

## How it works (architecture)

You run **two processes** in development: a **Python API** and a **Vite dev server** for the React UI. The UI proxies `/api` to the API (see `frontend/vite.config.ts`). All application data stays on disk under **`DATA_DIR`** (SQLite + file blobs), not in a hosted multi-tenant cloud.

```
  +---------------------------------------------------------------------+
  |                         Your machine                                 |
  |                                                                      |
  |   +------------------+          +----------------------------------+   |
  |   | Browser          |  HTTP    | FastAPI (async)                  |   |
  |   | React + TS       | -------> | /api/v1/*  + OpenAPI (Swagger) |   |
  |   | Vite :5173       |  proxy   | SQLAlchemy + aiosqlite           |   |
  |   +------------------+          +----------+-----------------------+   |
  |                                            |                         |
  |                                            v                         |
  |                              +---------------------------+           |
  |                              | DATA_DIR                  |           |
  |                              |  grantfiller.db (SQLite)  |           |
  |                              |  blobs/ (uploads, exports)|           |
  |                              |  app_preferences.json     |           |
  |                              +---------------------------+           |
  |                                            ^                         |
  |                              BackgroundTasks (parse, generate,      |
  |                              learn-org jobs)                         |
  |                                            |                         |
  |                              +-------------+-------------------+     |
  |                              | Ingest: PyMuPDF, python-docx,    |     |
  |                              | web (trafilatura, Playwright)   |     |
  |                              | Services: questions_extract,    |     |
  |                              | retrieve (embeddings), answers  |     |
  |                              +-------------+-------------------+     |
  |                                            |                         |
  |                              +-------------v-------------------+     |
  |                              | LLM + embeddings                 |     |
  |                              |  * Ollama (default, local)      |     |
  |                              |  * Google Gemini (API key)      |     |
  |                              +----------------------------------+     |
  +---------------------------------------------------------------------+
```

**Conceptual flow for one grant:** upload or fetch source → **parse** extracts text and builds **questions** → **generate** embeds the question, pulls top **facts** + **chunks**, calls the **LLM** → answers stored per question → **export** builds PDF/DOCX/MD from stored Q&A.

---

## Clone and install

### Prerequisites

- **Git**
- **Python 3.11+**
- **Node.js 18+** (for the frontend)
- An **LLM** path (pick one):
  - **[Ollama](https://ollama.com/)** installed and running, with a chat model pulled (default name in config: `qwen2.5:7b-instruct`), or
  - **[Google AI Studio](https://aistudio.google.com/apikey)** API key if you use **Gemini** (`LLM_PROVIDER=gemini`)

Optional but recommended:

- `ollama pull nomic-embed-text` — embeddings for smarter “learn facts” deduplication
- **Playwright Chromium** — `playwright install chromium` after Python deps (used when a grant URL is hard to extract as static HTML)

### 1. Clone the repository

```bash
git clone https://github.com/Ritesh-Senthil/grant_filler_local.git
cd grant_filler_local
```

(Use your fork or another remote URL if you prefer.)

### 2. Backend (Python API)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium
```

Copy environment defaults and adjust as needed. The API loads **`backend/.env`** by path (works no matter where you start `uvicorn` from):

```bash
cp ../.env.example .env
# Edit .env: DATA_DIR, OLLAMA_MODEL or GOOGLE_API_KEY + LLM_PROVIDER=gemini, etc.
```

### 3. Frontend (web UI)

```bash
cd ../frontend
npm install
```

---

## Run the application

You need **two terminals** (or equivalent).

**Terminal A — API**

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal B — UI**

```bash
cd frontend
npm run dev
```

Open **[http://localhost:5173](http://localhost:5173)**. The dev server proxies **`/api`** to **`http://127.0.0.1:8000`**.

**Suggested first run:** start **Ollama** (or set Gemini in `.env`), create a grant on the dashboard, upload a PDF or set a grant URL, run **Find questions**, then **Draft with AI** after adding a few **organization facts** under **Your organization**.

---

## Configure the AI backend

| Setting | Purpose |
|---------|---------|
| `LLM_PROVIDER` | `ollama` (default) or `gemini` |
| `OLLAMA_MODEL` / `OLLAMA_BASE_URL` | Must match `ollama list` and where Ollama listens |
| `GOOGLE_API_KEY` | Required when using Gemini |
| `DATA_DIR` | Folder for SQLite + `blobs/` (default `./data` relative to process cwd) |

The **Settings** page in the app can override **Ollama vs Gemini** without editing `.env`; that choice is stored under `DATA_DIR/app_preferences.json`. See **[.env.example](.env.example)** for all variables and comments.

---

## Optional: sample fixtures (PDFs & test website)

- **`testdata/grant_pdfs/*.pdf`** — Seven synthetic grant-style PDFs (easiest → hardest layout). Use them to try **Find questions in file**, then **Draft with AI**, without a real funder form.
- **`testdata/grant_web_fixture/`** — A static HTML “mini-grant” page for **URL import** testing (separate from the Vite app on port 5173).

Walkthroughs, file-by-file descriptions, and flows: **[testdata/README.md](testdata/README.md)**. Local test website (serve script and `WEB_FETCH_ALLOW_HTTP_LOCALHOST`): **[testdata/grant_web_fixture/README.md](testdata/grant_web_fixture/README.md)**.

---

## Where your data lives

- **`DATA_DIR`** (see `.env`) — contains **`grantfiller.db`** (SQLite), **`blobs/`** (uploads, exports), **`app_preferences.json`**, and optional **`enhancement_requests.jsonl`**.
- **Back up** the whole `DATA_DIR` folder to preserve grants and configuration.

---

## API reference

With the backend running: **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)** (Swagger UI).

---

## Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

```bash
cd frontend
npm test
```

Integration tests use Starlette’s **`TestClient`**; long-running **background jobs** may not fully mirror production timing under `pytest`. Job logic is also exercised in **`tests/test_job_runner_direct.py`**.

---

## Repository layout

```
grant_filler_local/
├── backend/           # FastAPI app (app/main.py, services/, tests/)
├── frontend/          # React + Vite + Tailwind
├── scripts/           # e.g. serve_grant_web_fixture.py, test PDF generators
├── testdata/          # Sample PDFs, web fixture (see testdata/README.md)
├── FEATURES.md        # Deep-dive features and operations
├── LICENSE            # MIT License
├── .env.example       # Copy to backend/.env
└── README.md          # This file
```

---

## Security note

There is **no built-in login** in this codebase. Anyone who can reach the UI and API on your network can use the app. For anything beyond **localhost**, put the stack behind a **VPN**, **SSH tunnel**, or **reverse proxy with authentication**. Be careful exposing **`WEB_FETCH_ALLOW_HTTP_LOCALHOST`** in untrusted environments (it allows the server to fetch specific **local HTTP** ports).

---

## License

This project is licensed under the **[MIT License](LICENSE)**.

GrantFiller produces **draft** content. Outputs still require **human review** before submission to any funder or third party; that is a matter of how you use the software, separate from the MIT terms above.
