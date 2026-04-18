"""Google Gemini (google-genai SDK): chat + embeddings. API key via GOOGLE_API_KEY / settings."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import Settings
from app.services.json_llm import chat_json_with_repair
from app.services.retry_remote import with_retries

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class GeminiClient:
    """Remote Gemini for chat + embeddings (implements LlmClient + Embedder protocols)."""

    def __init__(self, settings: Settings):
        key = (settings.google_api_key or "").strip()
        if not key:
            raise ValueError(
                "LLM_PROVIDER=gemini requires GOOGLE_API_KEY in the environment or backend/.env"
            )
        self._client = genai.Client(api_key=key)
        self.chat_model = settings.gemini_chat_model
        self.embed_model = settings.gemini_embed_model
        self._chat_timeout = min(settings.gemini_timeout_s, 600.0)
        self._embed_timeout = min(settings.gemini_embed_timeout_s, 180.0)

    def _run_chat(self, system: str, user: str) -> str:
        cfg = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.1,
        )
        resp = self._client.models.generate_content(
            model=self.chat_model,
            contents=user,
            config=cfg,
        )
        text = (resp.text or "").strip()
        if not text and resp.candidates:
            # Fallback: concatenate parts
            parts: list[str] = []
            for c in resp.candidates:
                if c.content and c.content.parts:
                    for p in c.content.parts:
                        if getattr(p, "text", None):
                            parts.append(p.text)
            text = "\n".join(parts).strip()
        return text

    async def chat(self, system: str, user: str) -> str:
        async def op() -> str:
            return await asyncio.wait_for(
                asyncio.to_thread(self._run_chat, system, user),
                timeout=self._chat_timeout,
            )

        return await with_retries(op, attempts=4)

    async def chat_json(self, system: str, user: str, response_model: type[BaseModel]) -> BaseModel:
        return await chat_json_with_repair(self.chat, system, user, response_model)

    def _run_embed(self, text: str) -> list[float]:
        resp = self._client.models.embed_content(
            model=self.embed_model,
            contents=text.strip() or ".",
            config=types.EmbedContentConfig(),
        )
        if not resp.embeddings:
            raise RuntimeError("Gemini embed_content returned no embeddings")
        emb = resp.embeddings[0]
        vals = emb.values
        if not vals:
            raise RuntimeError("Gemini embedding values empty")
        return [float(x) for x in vals]

    def _run_embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Single API call with list of strings if supported."""
        safe = [(t or "").strip() or "." for t in texts]
        resp = self._client.models.embed_content(
            model=self.embed_model,
            contents=safe,
            config=types.EmbedContentConfig(),
        )
        if not resp.embeddings or len(resp.embeddings) != len(safe):
            raise RuntimeError("Gemini batch embed length mismatch")
        out: list[list[float]] = []
        for e in resp.embeddings:
            if not e.values:
                raise RuntimeError("Gemini embedding values empty")
            out.append([float(x) for x in e.values])
        return out

    async def embed_text(self, text: str) -> list[float]:
        async def op() -> list[float]:
            return await asyncio.wait_for(
                asyncio.to_thread(self._run_embed, text),
                timeout=self._embed_timeout,
            )

        return await with_retries(op, attempts=3)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        async def op() -> list[list[float]]:
            return await asyncio.wait_for(
                asyncio.to_thread(self._run_embed_batch, texts),
                timeout=self._embed_timeout,
            )

        try:
            return await with_retries(op, attempts=3)
        except Exception as e:
            logger.warning("gemini batch embed failed, falling back to one-by-one: %s", e)
            sem = asyncio.Semaphore(8)

            async def one(t: str) -> list[float]:
                async with sem:
                    return await self.embed_text(t)

            return await asyncio.gather(*[one(t) for t in texts])
