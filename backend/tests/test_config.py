from pathlib import Path

from app.config import Settings
from app.main import _ollama_model_available


def test_relative_data_dir_is_anchored_to_backend(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    settings = Settings(data_dir=Path("stable-data"), database_url=None)
    assert settings.data_dir.name == "stable-data"
    assert settings.data_dir.parent.name == "backend"


def test_ollama_untagged_model_matches_latest_listing():
    installed = {"nomic-embed-text:latest", "qwen2.5:3b-instruct"}
    assert _ollama_model_available("nomic-embed-text", installed)
    assert _ollama_model_available("nomic-embed-text:latest", installed)
    assert _ollama_model_available("qwen2.5:3b-instruct", installed)
    assert not _ollama_model_available("qwen2.5:7b-instruct", installed)
