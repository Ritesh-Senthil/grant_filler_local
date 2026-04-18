"""Retry with backoff for transient remote LLM / API failures."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _is_transient_message(msg: str) -> bool:
    low = msg.lower()
    return any(
        x in low
        for x in (
            "429",
            "503",
            "resource exhausted",
            "unavailable",
            "timeout",
            "timed out",
            "rate",
            "overloaded",
            "try again",
        )
    )


async def with_retries(
    op: Callable[[], Awaitable[T]],
    *,
    attempts: int = 4,
    base_delay_s: float = 0.8,
    max_delay_s: float = 12.0,
) -> T:
    last: BaseException | None = None
    for i in range(attempts):
        try:
            return await op()
        except Exception as e:
            last = e
            msg = str(e)
            if i == attempts - 1 or not _is_transient_message(msg):
                raise
            delay = min(max_delay_s, base_delay_s * (2**i))
            logger.warning("remote_call_retry attempt=%s err=%s sleep=%.2fs", i + 1, msg[:200], delay)
            await asyncio.sleep(delay)
    assert last is not None
    raise last
