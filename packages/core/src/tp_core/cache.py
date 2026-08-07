"""Best-effort Redis cache-aside.

Wraps an async ``factory`` with a Redis cache: a JSON hit is validated via a Pydantic
``TypeAdapter`` and returned; a miss computes, stores (TTL), and returns. Caching is
BEST-EFFORT — any Redis error (including a failed connect) falls through to compute, so a
missing/broken cache never fails a request (and tests need no Redis). A tight connect
timeout keeps a down Redis from adding latency. Falsy results (None / [], usually a
transient tool failure) are NOT cached, so a blip can't pin a bad value for its whole TTL.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

import redis.asyncio as aioredis
from pydantic import TypeAdapter

from tp_core.settings import DEFAULT_REDIS_URL

# Per-tool TTLs in seconds, set by how fast each source actually changes.
TTL_GEOCODE = 30 * 24 * 3600
TTL_POIS = 7 * 24 * 3600
TTL_WEATHER = 6 * 3600
TTL_ROUTE = 7 * 24 * 3600
TTL_EMBED = 30 * 24 * 3600


def _redis_url() -> str:
    return os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)


async def cache_aside[T](
    key: str,
    ttl: int,
    factory: Callable[[], Awaitable[T]],
    adapter: TypeAdapter[T],
    *,
    cache_empty: bool = False,
) -> T:
    """Return ``key`` from Redis if present, else compute via ``factory`` and store it."""
    client: Any = None
    try:
        with suppress(Exception):  # any cache error -> fall through to compute
            client = aioredis.from_url(  # type: ignore[no-untyped-call]  # redis async API
                _redis_url(), socket_connect_timeout=0.25
            )
            raw = await client.get(key)
            if raw is not None:
                return adapter.validate_json(raw)
        value = await factory()
        if (value or cache_empty) and client is not None:
            with suppress(Exception):
                await client.set(key, adapter.dump_json(value), ex=ttl)
        return value
    finally:
        if client is not None:
            with suppress(Exception):
                await client.aclose()
