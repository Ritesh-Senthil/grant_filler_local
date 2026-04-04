# GrantFiller API

Local FastAPI backend. Run from repo root:

```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Requires Ollama running with `OLLAMA_MODEL` (default `qwen2.5:7b`).
