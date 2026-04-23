# GrantFiller — Setup Guide (v2)

**Local-first grant application assistant.** Upload a funder's PDF, Word file, or URL → GrantFiller extracts questions, drafts answers from your organization facts, and exports polished PDF / Word / Markdown.

> **Disclaimer:** GrantFiller produces **drafts**. Always review outputs before submitting to any funder. Licensed under the [MIT License](LICENSE).

This guide assumes you have **nothing installed yet**. Follow the steps top-to-bottom.

---

## Table of contents

1. [What you'll install](#1-what-youll-install)
2. [Install prerequisites (pick your OS)](#2-install-prerequisites-pick-your-os)
3. [Install and start Ollama (the local AI)](#3-install-and-start-ollama-the-local-ai)
4. [Clone the project](#4-clone-the-project)
5. [Set up the backend (Python API)](#5-set-up-the-backend-python-api)
6. [Set up the frontend (web UI)](#6-set-up-the-frontend-web-ui)
7. [Configure the application (`.env`)](#7-configure-the-application-env)
8. [Run the application](#8-run-the-application)
9. [Verify everything works](#9-verify-everything-works)
10. [First-time usage walkthrough](#10-first-time-usage-walkthrough)
11. [Alternative: use Google Gemini instead of Ollama](#11-alternative-use-google-gemini-instead-of-ollama)
12. [Troubleshooting](#12-troubleshooting)
13. [Uninstall / cleanup](#13-uninstall--cleanup)
14. [Architecture, data location, security](#14-architecture-data-location-security)

---

## 1. What you'll install

| Tool | Why |
|---|---|
| **Git** | To clone the repository |
| **Python 3.11+** | Runs the backend API |
| **Node.js 20+** | Runs the frontend web UI |
| **Ollama** + a model | Local AI that drafts your answers (default path) |

Hardware: the default chat model (`qwen2.5:3b-instruct`, ~**3B** parameters) is sized for **lighter machines** — aim for ~**4 GB free RAM** for the model plus OS overhead. For higher quality when you have more headroom, you can switch to `qwen2.5:7b-instruct` (see [Troubleshooting](#12-troubleshooting)).

---

## 2. Install prerequisites (pick your OS)

### macOS (Homebrew)

If you don't have Homebrew: install from <https://brew.sh>, then:

```bash
brew install git python@3.11 node
```

### Ubuntu / Debian / WSL (Ubuntu)

```bash
sudo apt update
sudo apt install -y git python3.11 python3.11-venv python3-pip build-essential
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### Amazon Linux 2023 / RHEL 9 / Fedora

```bash
sudo dnf install -y git python3.11 python3.11-pip
curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
sudo dnf install -y nodejs
```

### Windows (PowerShell as Administrator)

```powershell
winget install Git.Git
winget install Python.Python.3.11
winget install OpenJS.NodeJS.LTS
```

**Verify all three are installed** (run in a new terminal):

```bash
git --version
python3 --version     # Windows: python --version
node --version        # must be v20.x or higher
```

---

## 3. Install and start Ollama (the local AI)

### Install

Install Ollama via your package manager (CLI-only, no desktop app required):

- **macOS (Homebrew):**
  ```bash
  brew install ollama
  ```
- **Linux / WSL:**
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ```
- **Windows (winget, PowerShell as Administrator):**
  ```powershell
  winget install Ollama.Ollama
  ```

### Start Ollama

Ollama must be running in the background before you use GrantFiller. Start it in a dedicated terminal (or background it) — leave it running for as long as you use the app.

- **macOS (Homebrew):**
  ```bash
  brew services start ollama        # runs in background, auto-starts on login
  # or, foreground in a dedicated terminal:
  ollama serve
  ```
- **Linux (systemd):**
  ```bash
  sudo systemctl enable --now ollama
  ```
- **Linux / WSL (no systemd) or Windows:**
  ```bash
  ollama serve                      # foreground, in a dedicated terminal
  # or background it (Linux/WSL only):
  nohup ollama serve > ~/ollama.log 2>&1 &
  ```

> On Windows, the `winget` install may register Ollama as a service that starts automatically. If `curl http://localhost:11434/api/tags` already works, you're done — skip `ollama serve`.

### Verify Ollama is running

```bash
curl http://localhost:11434/api/tags
```

You should see a JSON response (likely `{"models":[]}` the first time).

### Pull the AI models

```bash
ollama pull qwen2.5:3b-instruct      # chat model — default (~3B, lower RAM than 7B)
ollama pull nomic-embed-text         # embeddings — recommended (better fact deduplication)
```

This downloads a few GB. Wait for each to finish.

---

## 4. Clone the project

Pick a folder where you want the project to live, then:

```bash
git clone https://github.com/Ritesh-Senthil/grant_filler_local.git
cd grant_filler_local
```

All remaining commands assume you are in this `grant_filler_local/` folder.

---

## 5. Set up the backend (Python API)

```bash
cd backend
python3 -m venv .venv
```

**Activate the virtual environment:**

- macOS / Linux / WSL: `source .venv/bin/activate`
- Windows PowerShell: `.venv\Scripts\Activate.ps1`
- Windows cmd: `.venv\Scripts\activate.bat`

Then install dependencies:

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

**Optional** — only needed if you want to import grants from JavaScript-heavy websites:

```bash
playwright install chromium
# Linux may also need:
playwright install-deps chromium     # may prompt for sudo
```

---

## 6. Set up the frontend (web UI)

Open a **new terminal**, navigate back to the repo root, then:

```bash
cd frontend
npm install
```

---

## 7. Configure the application (`.env`)

From the **repo root**, copy the example config into the backend folder:

- macOS / Linux / WSL:
  ```bash
  cp .env.example backend/.env
  ```
- Windows cmd:
  ```cmd
  copy .env.example backend\.env
  ```
- Windows PowerShell:
  ```powershell
  Copy-Item .env.example backend\.env
  ```

The defaults in `.env.example` are already set up for Ollama — **no edits needed** for a standard local setup.

Key values in `backend/.env`:

```ini
DATA_DIR=./data
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:3b-instruct
```

> The API always reads **`backend/.env`** (not a file in the repo root). Restart the API after any changes.

---

## 8. Run the application

You need **two terminals running at the same time**.

### Terminal A — backend API

From the repo root:

```bash
cd backend
source .venv/bin/activate            # Windows PS: .venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Wait for `Application startup complete.` in the logs.

### Terminal B — frontend UI

From the repo root:

```bash
cd frontend
npm run dev
```

Wait for a line like `Local: http://localhost:5173/`.

---

## 9. Verify everything works

- Open the UI: <http://localhost:5173>
- Open the API docs: <http://127.0.0.1:8000/docs>
- Confirm Ollama has the model: `curl http://localhost:11434/api/tags` (should list `qwen2.5:3b-instruct`)

The SQLite database and `blobs/` folder are created automatically under `DATA_DIR` on first API start.

---

## 10. First-time usage walkthrough

1. Go to <http://localhost:5173>.
2. Open **Your organization** and add a few facts about your org (mission, programs, budget, past grants, etc.). These are reused across grants.
3. From the dashboard, **create a grant**.
4. Upload a PDF/DOCX **or** paste a grant URL.
   - Want to try without a real grant? Use the sample PDFs in `testdata/grant_pdfs/` — see [testdata/README.md](testdata/README.md).
5. Click **Find questions** to parse the form.
6. Click **Draft with AI** to generate answers.
7. Review, edit, then **Export** to PDF / DOCX / Markdown.

---

## 11. Alternative: use Google Gemini instead of Ollama

If you don't want to run a local LLM, you can use Gemini (cloud):

1. Create a free API key at <https://aistudio.google.com/apikey>.
2. Edit `backend/.env` and add:
   ```ini
   LLM_PROVIDER=gemini
   GOOGLE_API_KEY=your-key-here
   ```
3. Restart the backend (Terminal A).

> You can also switch Ollama ↔ Gemini at runtime from the **Settings** page in the app. That choice is stored in `DATA_DIR/app_preferences.json`.
>
> Note: Gemini handles chat, but embeddings (used for fact deduplication) still default to Ollama's `nomic-embed-text`. For a fully cloud setup you can skip Ollama — some features fall back to simpler matching. See `.env.example`.

---

## 12. Troubleshooting

| Symptom | Fix |
|---|---|
| `ollama: command not found` or LLM calls hang | Ollama isn't running. Start the Ollama app (macOS/Windows) or `ollama serve` (Linux). Verify: `curl http://localhost:11434/api/tags`. |
| `model 'qwen2.5:3b-instruct' not found` | Run `ollama pull qwen2.5:3b-instruct`, or change `OLLAMA_MODEL` in `backend/.env` to a model you already have (`ollama list`). |
| Out-of-memory when drafting | Default 3B still too tight, or concurrent jobs. Try a smaller chat model (e.g. `phi3:mini`, `gemma2:2b`) and set `OLLAMA_MODEL` accordingly, close other apps, or reduce parallel parse load in `.env`. If you have **8+ GB** free RAM, `qwen2.5:7b-instruct` often gives better answers. |
| Port 8000 or 5173 already in use | Run uvicorn on another port (`--port 8010`) and update `frontend/vite.config.ts` proxy target, or start Vite on another port: `npm run dev -- --port 5174`. |
| Frontend shows `ECONNREFUSED` / `/api` 502 | Backend isn't running, or is on a different port than the proxy expects. Start Terminal A first. |
| `.env` values ignored | File must be at **`backend/.env`**, not repo root. Restart uvicorn after edits. |
| `pip install -e ".[dev]"` fails building a wheel | Upgrade pip (`python -m pip install --upgrade pip`); Linux: `sudo apt install build-essential python3-dev`; macOS: `xcode-select --install`. |
| `playwright install chromium` fails on Linux | `playwright install-deps chromium` (may need sudo). |
| Gemini returns 401 / 403 | `GOOGLE_API_KEY` missing or invalid; confirm `LLM_PROVIDER=gemini` in `backend/.env` and restart the API. |

---

## 13. Uninstall / cleanup

```bash
# From repo root:
rm -rf backend/.venv          # remove Python venv
rm -rf frontend/node_modules  # remove npm packages
rm -rf data                   # remove all app data (grants, uploads, exports)
```

To remove the project entirely, delete the `grant_filler_local/` folder.
To remove the default chat model: `ollama rm qwen2.5:3b-instruct`.

---

## 14. Architecture, data location, security

**Two processes in development:** a Python FastAPI backend and a Vite dev server for the React UI. The UI proxies `/api` to the API (see `frontend/vite.config.ts`). All data stays on your machine under `DATA_DIR`.

```
+---------------------------------------------------------------------+
|                         Your machine                                |
|                                                                     |
|   +------------------+          +----------------------------------+|
|   | Browser          |  HTTP    | FastAPI (async)                  ||
|   | React + TS       | -------> | /api/v1/*  + OpenAPI (Swagger)   ||
|   | Vite :5173       |  proxy   | SQLAlchemy + aiosqlite           ||
|   +------------------+          +----------+-----------------------+|
|                                            |                        |
|                                            v                        |
|                              +---------------------------+          |
|                              | DATA_DIR                  |          |
|                              |  grantfiller.db (SQLite)  |          |
|                              |  blobs/ (uploads, exports)|          |
|                              |  app_preferences.json     |          |
|                              +---------------------------+          |
|                                                                     |
|                              LLM + embeddings                       |
|                                * Ollama (default, local)            |
|                                * Google Gemini (API key)            |
+---------------------------------------------------------------------+
```

**Data location:** everything lives in `DATA_DIR` (default `./data` relative to the backend's working directory) — `grantfiller.db`, `blobs/`, `app_preferences.json`. **Back up this folder** to preserve your work.

**Security:** there is **no built-in login**. Anyone who can reach the UI and API on your network can use the app. For anything beyond `localhost`, put it behind a VPN, SSH tunnel, or reverse proxy with authentication. Be careful with `WEB_FETCH_ALLOW_HTTP_LOCALHOST` in untrusted environments.

**For feature details:** see [FEATURES.md](FEATURES.md).
**For sample test data:** see [testdata/README.md](testdata/README.md).

---

## License

MIT — see [LICENSE](LICENSE). GrantFiller produces draft content; human review before submission is your responsibility.
