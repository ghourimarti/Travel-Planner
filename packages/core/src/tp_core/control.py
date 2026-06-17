"""Runtime kill switch (S10b, Decision 20).

A Redis flag (``planning:enabled``) ops can flip live with no redeploy
(``redis-cli set planning:enabled 0``) to stop accepting new planning runs — a cost
circuit-breaker checked at dispatch. FAIL-OPEN: a missing key or a Redis blip leaves
planning ENABLED, so an infra hiccup can't take the product down; only an explicit
disable stops it.
"""

from __future__ import annotations

import os
from contextlib import suppress
from typing import Any

import redis.asyncio as aioredis

from tp_core.settings import DEFAULT_REDIS_URL

_KEY = "planning:enabled"
_DISABLED = {b"0", b"false", "0", "false"}


def _redis_url() -> str:
    return os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)


async def planning_enabled() -> bool:
    """True unless the kill switch is explicitly set to disabled (fail-open)."""
    client: Any = None
    try:
        with suppress(Exception):
            client = aioredis.from_url(  # type: ignore[no-untyped-call]  # redis async API
                _redis_url(), socket_connect_timeout=0.25
            )
            value = await client.get(_KEY)
            if value is not None:
                return value not in _DISABLED
        return True
    finally:
        if client is not None:
            with suppress(Exception):
                await client.aclose()
