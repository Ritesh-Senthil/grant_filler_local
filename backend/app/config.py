from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always resolve to backend/.env (next to the `app` package), not cwd — so `GOOGLE_API_KEY` etc. load
# when uvicorn is started from the repo root or any other directory.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_DOTENV = _BACKEND_ROOT / ".env"


def _settings_config() -> SettingsConfigDict:
    kw: dict = {"env_file_encoding": "utf-8", "extra": "ignore"}
    if _BACKEND_DOTENV.is_file():
        kw["env_file"] = _BACKEND_DOTENV
    return SettingsConfigDict(**kw)


class Settings(BaseSettings):
    model_config = _settings_config()

    data_dir: Path = Path("./data")
    database_url: str | None = None  # if unset, uses data_dir/grantfiller.db
    # llm_provider: ollama (local) or gemini (Google AI Studio API key)
    llm_provider: Literal["ollama", "gemini"] = "ollama"
    google_api_key: str | None = None
    # Stable IDs — see https://ai.google.dev/gemini-api/docs/models (2.0 Flash is deprecated for new users)
    gemini_chat_model: str = "gemini-2.5-flash"
    gemini_embed_model: str = "gemini-embedding-001"
    gemini_timeout_s: float = 120.0
    gemini_embed_timeout_s: float = 90.0
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:3b-instruct"
    ollama_timeout_s: float = 600.0
    # Embeddings for semantic deduplication when learning org facts (ollama pull nomic-embed-text)
    ollama_embed_model: str = "nomic-embed-text"
    learn_org_embed_enabled: bool = True
    # Cosine similarity threshold: proposed fact merges into existing if >= this (0–1).
    learn_org_semantic_similarity: float = 0.78
    # Max grant text chunks merged into answer drafting retrieval (embedding cost / context).
    grant_retrieval_chunk_cap: int = 96
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    @field_validator("grant_retrieval_chunk_cap", mode="before")
    @classmethod
    def _normalize_grant_chunk_cap(cls, v: object) -> int:
        """0 or invalid env values would otherwise mean 'no cap' in retrieval — coerce to a sane default."""
        if v is None or v == "":
            return 96
        try:
            n = int(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 96
        if n <= 0:
            return 96
        return min(n, 500)
    max_upload_mb: int = 50
    # Parse pipeline: larger chunks = fewer LLM calls; concurrency runs chunks in parallel (bounded for Ollama).
    chunk_max_chars: int = 32000
    chunk_overlap: int = 400
    parse_chunk_concurrency: int = 3
    # Web import (HTTPS fetch for parse-from-URL)
    web_fetch_timeout_s: float = 45.0
    web_fetch_max_bytes: int = 8_000_000
    web_min_extracted_chars: int = 200
    web_fetch_user_agent: str = "GrantFiller/0.1 (+local; contact: admin)"
    # trust_env=False: ignore HTTP(S)_PROXY so local ngrok URLs are not sent through a corporate proxy (fixes SSL errors).
    web_fetch_trust_env: bool = False
    # Set to false only for debugging (insecure). Prefer fixing CA bundle / proxy instead.
    web_fetch_ssl_verify: bool = True
    # Dev only: allow http://127.0.0.1 or http://localhost on WEB_FETCH_HTTP_LOCAL_PORTS (fixture site; no ngrok).
    web_fetch_allow_http_localhost: bool = False
    web_fetch_http_local_ports: str = "8765,8080,3000"
    # After static HTTP + trafilatura, retry with headless Chromium if text is still too short (JS-heavy portals).
    web_fetch_playwright: bool = True
    web_fetch_playwright_timeout_ms: int = 45_000
    web_fetch_playwright_post_load_ms: int = 2_000
    # Developer credits (read-only in UI; from env — not org-editable)
    grantfiller_dev_display_name: str = ""
    grantfiller_dev_github_url: str = ""
    grantfiller_dev_linkedin_url: str = ""
    grantfiller_dev_sponsor_text: str = ""
    grantfiller_dev_sponsor_url: str = ""

