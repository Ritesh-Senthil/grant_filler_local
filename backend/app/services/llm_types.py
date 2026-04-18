"""Protocols for chat and embedding backends (Ollama, Gemini, etc.)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class LlmClient(Protocol):
    async def chat(self, system: str, user: str) -> str: ...

    async def chat_json(self, system: str, user: str, response_model: type[BaseModel]) -> BaseModel: ...


@runtime_checkable
class Embedder(Protocol):
    async def embed_text(self, text: str) -> list[float]: ...

    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...
