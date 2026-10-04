"""User preferences stored under DATA_DIR (survives restarts; overrides env for selected keys)."""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Literal

_PREF_FILE = "app_preferences.json"
_LOCALE_RE = re.compile(r"^[a-zA-Z0-9._-]{1,32}$")
_PREF_LOCK = threading.Lock()


def preferences_path(data_dir: Path) -> Path:
    return (data_dir / _PREF_FILE).resolve()


def _load_dict(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _write_dict(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def load_llm_provider_override(data_dir: Path) -> Literal["ollama", "gemini"] | None:
    """Return saved provider if valid; None means use Settings.llm_provider from env."""
    path = preferences_path(data_dir)
    with _PREF_LOCK:
        raw = _load_dict(path)
        p = raw.get("llm_provider")
        if p in ("ollama", "gemini"):
            return p
    return None


def save_llm_provider_override(data_dir: Path, provider: Literal["ollama", "gemini"]) -> None:
    path = preferences_path(data_dir)
    with _PREF_LOCK:
        data = _load_dict(path)
        data["llm_provider"] = provider
        _write_dict(path, data)


def clear_llm_provider_override(data_dir: Path) -> None:
    """Remove saved provider so env / LLM_PROVIDER applies again."""
    path = preferences_path(data_dir)
    with _PREF_LOCK:
        if not path.is_file():
            return
        data = _load_dict(path)
        data.pop("llm_provider", None)
        if data:
            _write_dict(path, data)
        else:
            path.unlink(missing_ok=True)


def user_llm_override_exists(data_dir: Path) -> bool:
    """True when app_preferences.json contains a valid llm_provider (user chose in UI)."""
    return load_llm_provider_override(data_dir) is not None


def load_locale_override(data_dir: Path) -> str | None:
    """Saved locale string (e.g. iso, en-US). None means use UI default until persisted."""
    path = preferences_path(data_dir)
    with _PREF_LOCK:
        raw = _load_dict(path)
        loc = raw.get("locale")
        if isinstance(loc, str) and _LOCALE_RE.match(loc.strip()):
            return loc.strip()
    return None


def save_locale_override(data_dir: Path, locale: str) -> None:
    loc = locale.strip()
    if not _LOCALE_RE.match(loc):
        raise ValueError("Invalid locale")
    path = preferences_path(data_dir)
    with _PREF_LOCK:
        data = _load_dict(path)
        data["locale"] = loc
        _write_dict(path, data)
