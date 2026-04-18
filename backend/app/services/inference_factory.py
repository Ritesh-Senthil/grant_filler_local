"""Construct LLM + embedder pair from settings (Ollama local or Gemini remote)."""

from __future__ import annotations

from app.config import Settings
from app.services.gemini_client import GeminiClient
from app.services.llm_types import Embedder, LlmClient
from app.services.ollama import OllamaClient


def build_llm_and_embedder(settings: Settings) -> tuple[LlmClient, Embedder]:
    if settings.llm_provider == "gemini":
        g = GeminiClient(settings)
        return g, g
    o = OllamaClient(settings)
    return o, o
