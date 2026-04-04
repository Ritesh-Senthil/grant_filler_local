# GrantFiller (local)

Local-first app to **extract grant application questions** from PDF/DOCX and **draft answers** from your organization profile and facts (via **Ollama**). Review answers, then **export a Q&A PDF**.

## Prerequisites

- Python 3.11+
- Node 18+
- [Ollama](https://ollama.com/) running locally with a capable model (default in config: `qwen2.5:7b`)

## Quick start

1. **Ollama** — pull a model, e.g. `ollama pull qwen2.5:7b`.

2. **Backend**
   ```bash
   cd backend
   python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   playwright install chromium   # needed for “paste URL” on JS-heavy grant portals
   cp ../.env.example .env   # optional; edit OLLAMA_MODEL / DATA_DIR
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

3. **Frontend** (new terminal)
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. Open **http://localhost:5173** — API is proxied to `http://127.0.0.1:8000`.

## Data & backup

- SQLite database and uploaded files live under **`DATA_DIR`** (default `./data` relative to where you start the API).
- Back up that folder to preserve grants and org profile.

## API docs

With the backend running: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Tests

```bash
cd backend && source .venv/bin/activate && pytest
```

- **API tests** use Starlette `TestClient`; **async `BackgroundTasks` are not guaranteed to finish** in that environment the same way as under `uvicorn`, so enqueue-only checks live in `tests/test_api_integration.py`.
- **Job completion** (parse → questions, generate → answers) is covered in `tests/test_job_runner_direct.py` by calling `run_parse_job` / `run_generate_job` with `asyncio.run`.

## License

Use at your own risk; outputs require human review before submission.
