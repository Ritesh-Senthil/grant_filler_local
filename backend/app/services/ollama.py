import httpx
from pydantic import BaseModel

from app.config import Settings
from app.services.json_llm import chat_json_with_repair


def _ollama_error_body(r: httpx.Response) -> str | None:
    try:
        data = r.json()
        err = data.get("error")
        return str(err) if err is not None else None
    except Exception:
        return None


def _is_model_not_found(status: int, error_msg: str | None) -> bool:
    if status != 404 or not error_msg:
        return False
    low = error_msg.lower()
    return "not found" in low and "model" in low


class OllamaClient:
    """Local Ollama: chat + embeddings (implements LlmClient + Embedder protocols)."""

    def __init__(self, settings: Settings):
        self.base = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.embed_model = settings.ollama_embed_model
        self.timeout = settings.ollama_timeout_s

    def _ollama_troubleshoot_hint(self) -> str:
        return (
            f" Is Ollama running? Try: curl {self.base}/api/tags "
            f"and ollama pull {self.model}. OLLAMA_BASE_URL should be the server root (e.g. http://127.0.0.1:11434) with no /v1 path."
        )

    def _model_not_found_message(self, detail: str | None) -> str:
        return (
            f"Ollama: {detail or 'model not found'}. "
            f"Set OLLAMA_MODEL to an exact name from `ollama list` (e.g. qwen2.5:3b-instruct, not qwen2.5:3b unless you pulled that tag)."
        )

    async def _chat_via_generate(self, client: httpx.AsyncClient, system: str, user: str) -> str:
        """Fallback for Ollama builds or proxies that do not expose POST /api/chat (404)."""
        prompt = f"### System instructions\n{system}\n\n### User message\n{user}"
        r = await client.post(
            f"{self.base}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1},
            },
        )
        err = _ollama_error_body(r)
        if _is_model_not_found(r.status_code, err):
            raise RuntimeError(self._model_not_found_message(err))
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"{e}{self._ollama_troubleshoot_hint()}") from e
        data = r.json()
        return (data.get("response") or "").strip()

    async def chat(self, system: str, user: str) -> str:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(f"{self.base}/api/chat", json=body)
            err = _ollama_error_body(r)
            if r.status_code == 404:
                if _is_model_not_found(404, err):
                    raise RuntimeError(self._model_not_found_message(err))
                return await self._chat_via_generate(client, system, user)
            try:
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"{e}{self._ollama_troubleshoot_hint()}") from e
            data = r.json()
            msg = data.get("message") or {}
            return msg.get("content") or ""

    async def chat_json(self, system: str, user: str, response_model: type[BaseModel]) -> BaseModel:
        return await chat_json_with_repair(self.chat, system, user, response_model)

    async def embed_text(self, text: str) -> list[float]:
        """Single text embedding via Ollama /api/embeddings (tries `input` then `prompt`)."""
        t = (text or "").strip() or "."
        last_err: str | None = None
        async with httpx.AsyncClient(timeout=min(self.timeout, 120.0)) as client:
            for key in ("input", "prompt"):
                r = await client.post(
                    f"{self.base}/api/embeddings",
                    json={"model": self.embed_model, key: t},
                )
                err = _ollama_error_body(r)
                if _is_model_not_found(r.status_code, err):
                    raise RuntimeError(
                        f"Ollama embedding model not found: {self.embed_model}. "
                        f"Run: ollama pull {self.embed_model}"
                    ) from None
                if r.status_code != 200:
                    last_err = err or r.text or str(r.status_code)
                    continue
                data = r.json()
                emb = data.get("embedding")
                if isinstance(emb, list) and emb and isinstance(emb[0], (int, float)):
                    return [float(x) for x in emb]
                last_err = "missing embedding in response"
        raise RuntimeError(
            f"Ollama embeddings failed ({self.embed_model}): {last_err or 'unknown'}. "
            f"Install with: ollama pull {self.embed_model}"
        )

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed many strings in parallel (bounded concurrency)."""
        import asyncio

        safe = [(t or "").strip() or "." for t in texts]
        sem = asyncio.Semaphore(8)

        async def bounded(s: str) -> list[float]:
            async with sem:
                return await self.embed_text(s)

        return await asyncio.gather(*[bounded(t) for t in safe])
