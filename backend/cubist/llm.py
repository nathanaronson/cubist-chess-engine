"""Shared Anthropic client. Person E owns; A and C use it.

Single shared async client + global semaphore + retry. Every LLM call in
the system goes through here so we have one place to tune concurrency and
rate-limit handling.
"""

from __future__ import annotations

import asyncio
from typing import Any

from anthropic import AsyncAnthropic
from anthropic._exceptions import APIError, RateLimitError

from cubist.config import settings

_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
_sem = asyncio.Semaphore(30)


async def complete(
    model: str,
    system: str,
    user: str,
    max_tokens: int = 256,
    tools: list[dict] | None = None,
) -> Any:
    """One-shot chat call. Returns the raw `message.content` list.

    For text replies, take `content[0].text`. For tool-use replies, look for
    a `tool_use` block and read its `input` dict.
    """
    backoff = 1.0
    async with _sem:
        for attempt in range(5):
            try:
                msg = await _client.messages.create(
                    model=model,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                    max_tokens=max_tokens,
                    tools=tools or [],
                )
                return msg.content
            except RateLimitError:
                await asyncio.sleep(backoff)
                backoff *= 2
            except APIError:
                if attempt == 4:
                    raise
                await asyncio.sleep(backoff)
                backoff *= 2
    raise RuntimeError("unreachable")


async def complete_text(model: str, system: str, user: str, max_tokens: int = 256) -> str:
    """Convenience wrapper for plain-text replies."""
    content = await complete(model, system, user, max_tokens=max_tokens)
    for block in content:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""
