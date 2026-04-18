"""Shared JSON extraction and repair for LLM chat outputs."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def first_balanced_json_object(s: str) -> str | None:
    """Return the first top-level `{...}` slice so trailing junk does not break parsing."""
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


def extract_json(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    balanced = first_balanced_json_object(text)
    if balanced is not None:
        return balanced
    return text


async def chat_json_with_repair(
    chat: Callable[[str, str], Awaitable[str]],
    system: str,
    user: str,
    response_model: type[T],
) -> T:
    """Parse JSON from chat output; on failure, one repair round with a stricter system prompt."""
    raw = await chat(system, user)
    text = extract_json(raw)
    try:
        return response_model.model_validate_json(text)
    except Exception:
        repair_user = (
            user
            + "\n\nYour previous reply was not valid JSON. Reply with ONLY a single JSON value, no markdown."
        )
        raw2 = await chat(
            "You output only valid JSON. No prose, no markdown fences.",
            repair_user,
        )
        text2 = extract_json(raw2)
        return response_model.model_validate_json(text2)
