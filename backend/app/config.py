import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    data_dir: Path = Path("./data")
    database_url: str | None = None  # if unset, uses data_dir/grantfiller.db
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    ollama_timeout_s: float = 600.0
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
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

