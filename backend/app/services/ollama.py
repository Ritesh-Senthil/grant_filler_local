import json
import re

import httpx
from pydantic import BaseModel

from app.config import Settings


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
    def __init__(self, settings: Settings):
        self.base = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout_s

    def _ollama_troubleshoot_hint(self) -> str:
        return (
            f" Is Ollama running? Try: curl {self.base}/api/tags "
            f"and ollama pull {self.model}. OLLAMA_BASE_URL should be the server root (e.g. http://127.0.0.1:11434) with no /v1 path."
        )

    def _model_not_found_message(self, detail: str | None) -> str:
        return (
            f"Ollama: {detail or 'model not found'}. "
            f"Set OLLAMA_MODEL to an exact name from `ollama list` (e.g. qwen2.5:7b-instruct, not qwen2.5:7b unless you pulled that tag)."
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
        raw = await self.chat(system, user)
        text = _extract_json(raw)
        try:
            return response_model.model_validate_json(text)
        except Exception:
            repair_user = (
                user
                + "\n\nYour previous reply was not valid JSON. Reply with ONLY a single JSON value, no markdown."
            )
            raw2 = await self.chat(
                "You output only valid JSON. No prose, no markdown fences.",
                repair_user,
            )
            text2 = _extract_json(raw2)
            return response_model.model_validate_json(text2)


def _first_balanced_json_object(s: str) -> str | None:
    """Return the first top-level `{...}` slice so extra `}` or prose after valid JSON does not break parsing."""
    s = s.strip()
    start = s.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


def _extract_json(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    balanced = _first_balanced_json_object(text)
    if balanced is not None:
        return balanced
    return text
