"""Shared async HTTP with timeout + retry/backoff.

Resilience scope for this layer (Step 3): per-call timeout and bounded retries
with exponential backoff + jitter, retrying only *transient* failures (network
errors, 5xx, 429) — never 4xx (those won't fix on retry). Circuit breakers and
the full degradation matrix are added in Step 11.
"""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from tp_core.exceptions import CustomException
from tp_core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_TIMEOUT = 15.0
_USER_AGENT = "ai-travel-planner/0.1 (portfolio project)"


class ToolError(CustomException):
    """A tool's external call failed (after retries)."""


class _RetryableError(Exception):
    """Transient upstream failure (5xx / 429) worth retrying."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.5, max=4.0),
    retry=retry_if_exception_type((httpx.TransportError, _RetryableError)),
    reraise=True,
)
async def _request_json(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": _USER_AGENT}) as client:
        response = await client.request(method, url, params=params, data=data)
    if response.status_code >= 500 or response.status_code == 429:
        raise _RetryableError(f"{url} returned {response.status_code}")
    response.raise_for_status()
    return response.json()


async def fetch_json(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """GET/POST a URL and return parsed JSON, or raise :class:`ToolError`."""
    try:
        return await _request_json(method, url, params=params, data=data, timeout=timeout)
    except Exception as exc:
        logger.warning("tool HTTP call failed: %s %s (%s)", method, url, exc.__class__.__name__)
        raise ToolError(f"request to {url} failed", exc) from exc
