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

from tp_core.llm.circuit import infra_breaker
from tp_core.metrics import record_cache
from tp_core.settings import DEFAULT_REDIS_URL

# Per-tool TTLs in seconds, set by how fast each source actually changes.
TTL_GEOCODE = 30 * 24 * 3600
TTL_POIS = 7 * 24 * 3600
TTL_WEATHER = 6 * 3600
TTL_ROUTE = 7 * 24 * 3600
TTL_EMBED = 30 * 24 * 3600


def _redis_url() -> str:
    return os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)


def cache_version() -> str:
    """Composite version prefix for every cache key.

    Bump any component and the OLD entries are orphaned: nothing reads them again and
    their own TTL reaps them. The alternative is FLUSHDB, which is indiscriminate —
    it also discards the geocode and POI entries that a prompt change did not
    invalidate, so a one-line prompt edit costs a full cold cache.

    Read from the environment rather than Settings for the same reason control.py
    does: this is on the request path, and a missing provider key must not turn a
    cache lookup into a config error.
    """
    return "{}.{}.{}".format(
        os.environ.get("PROMPT_VERSION", "v1"),
        os.environ.get("CORPUS_VERSION", "v1"),
        os.environ.get("INDEX_VERSION", "v1"),
    )


async def cache_aside[T](
    key: str,
    ttl: int,
    factory: Callable[[], Awaitable[T]],
    adapter: TypeAdapter[T],
    *,
    cache_empty: bool = False,
) -> T:
    """Return ``key`` from Redis if present, else compute via ``factory`` and store it."""
    vkey = f"{cache_version()}:{key}"
    breaker = infra_breaker("redis")

    # An OPEN breaker SKIPS Redis entirely rather than suppressing its error. The
    # difference is latency, not correctness: `suppress` still pays the 0.25s connect
    # timeout on EVERY call while Redis is down, which turns a dead cache into added
    # latency on 100% of traffic — the same failure the venue breaker exists to stop.
    tool = key.split(":", 1)[0]  # bounded label: the tool name, never the full key
    client: Any = None
    if not breaker.allows("redis"):
        record_cache(tool, "skipped")
        return await factory()

    try:
        try:
            client = aioredis.from_url(  # type: ignore[no-untyped-call]  # redis async API
                _redis_url(), socket_connect_timeout=0.25
            )
            raw = await client.get(vkey)
            breaker.record_success("redis")
            if raw is not None:
                record_cache(tool, "hit")
                return adapter.validate_json(raw)
            record_cache(tool, "miss")
        except Exception:  # any cache error -> fall through to compute (fail-open)
            breaker.record_failure("redis")
            record_cache(tool, "error")
        value = await factory()
        if (value or cache_empty) and client is not None:
            with suppress(Exception):
                await client.set(vkey, adapter.dump_json(value), ex=ttl)
        return value
    finally:
        if client is not None:
            with suppress(Exception):
                await client.aclose()
