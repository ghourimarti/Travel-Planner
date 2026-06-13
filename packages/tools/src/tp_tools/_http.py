"""Resilient async HTTP for the tools: timeout, User-Agent, retry/backoff, typed errors.

Every external call goes through here, so each tool inherits the same resilience
and the same Retryable/NonRetryable classification the agent can reason about.
"""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from tp_core.exceptions import NonRetryableToolError, RetryableToolError
from tp_core.logging import get_logger

_log = get_logger("tp_tools.http")

# Nominatim / OSRM usage policies require a valid, identifying User-Agent.
USER_AGENT = "ai-travel-planner/0.1 (https://github.com/example/ai-travel-planner)"
DEFAULT_TIMEOUT_S = 15.0
_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def _client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )


@retry(
    retry=retry_if_exception_type(RetryableToolError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=8),
    reraise=True,
)
async def request_json(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> Any:
    """Make a request and return parsed JSON; retry transient failures, classify the rest."""
    try:
        async with _client(timeout) as client:
            resp = await client.request(method, url, params=params, data=data, headers=headers)
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        _log.warning("tool_http_transport_error", url=url, error=str(exc))
        raise RetryableToolError(f"{method} {url} failed: {type(exc).__name__}") from exc

    if resp.status_code in _RETRYABLE_STATUS:
        raise RetryableToolError(f"{method} {url} -> {resp.status_code}")
    if resp.status_code >= 400:
        raise NonRetryableToolError(f"{method} {url} -> {resp.status_code}: {resp.text[:200]}")
    return resp.json()


async def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> Any:
    return await request_json("GET", url, params=params, headers=headers, timeout=timeout)


async def post_json(
    url: str, *, data: dict[str, Any] | None = None, timeout: float = DEFAULT_TIMEOUT_S
) -> Any:
    return await request_json("POST", url, data=data, timeout=timeout)
