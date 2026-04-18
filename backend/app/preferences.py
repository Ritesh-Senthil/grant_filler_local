"""User preferences stored under DATA_DIR (survives restarts; overrides env for selected keys)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

_PREF_FILE = "app_preferences.json"
_LOCALE_RE = re.compile(r"^[a-zA-Z0-9._-]{1,32}$")


def preferences_path(data_dir: Path) -> Path:
    return (data_dir / _PREF_FILE).resolve()


def load_llm_provider_override(data_dir: Path) -> Literal["ollama", "gemini"] | None:
    """Return saved provider if valid; None means use Settings.llm_provider from env."""
    path = preferences_path(data_dir)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        p = raw.get("llm_provider")
        if p in ("ollama", "gemini"):
            return p
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return None


def save_llm_provider_override(data_dir: Path, provider: Literal["ollama", "gemini"]) -> None:
    path = preferences_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except (OSError, json.JSONDecodeError):
            data = {}
    data["llm_provider"] = provider
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def clear_llm_provider_override(data_dir: Path) -> None:
    """Remove saved provider so env / LLM_PROVIDER applies again."""
    path = preferences_path(data_dir)
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            path.unlink(missing_ok=True)
            return
        data.pop("llm_provider", None)
        if data:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        else:
            path.unlink()
    except (OSError, json.JSONDecodeError):
        path.unlink(missing_ok=True)


def user_llm_override_exists(data_dir: Path) -> bool:
    """True when app_preferences.json contains a valid llm_provider (user chose in UI)."""
    return load_llm_provider_override(data_dir) is not None


def load_locale_override(data_dir: Path) -> str | None:
    """Saved locale string (e.g. iso, en-US). None means use UI default until persisted."""
    path = preferences_path(data_dir)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        loc = raw.get("locale")
        if isinstance(loc, str) and _LOCALE_RE.match(loc.strip()):
            return loc.strip()
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return None


def save_locale_override(data_dir: Path, locale: str) -> None:
    loc = locale.strip()
    if not _LOCALE_RE.match(loc):
        raise ValueError("Invalid locale")
    path = preferences_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except (OSError, json.JSONDecodeError):
            data = {}
    data["locale"] = loc
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
