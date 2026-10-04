"""App-wide call spacing for a rate-limited UPSTREAM (public Nominatim: max 1 request/s).

The limit belongs to the upstream, not to a tenant, so it must hold across every worker
process at once: a 3-city trip alone geocodes three cities concurrently, and one burst of
abuse traffic sent ~300 lookups in 90 s and got this deployment refused (HTTP 429) for
~20 minutes (2026-09-30).

A slot is a Redis key set with NX and a PX expiry of one interval: whoever sets it may
make ONE call; everyone else waits for it to expire. A caller that cannot get a slot
within its wait budget gets ``ThrottledError`` - the plan declines as "busy" instead of
adding to a burst that would get everybody refused.

If Redis is unreachable the spacing falls back to THIS process alone: fail-open for
availability, but never unthrottled.
"""

from __future__ import annotations

import asyncio
import os
import random
import time
import weakref
from typing import Any

import redis.asyncio as aioredis

from tp_core.exceptions import NonRetryableToolError
from tp_core.metrics import record_error
from tp_core.settings import DEFAULT_REDIS_URL

# One pooled client per EVENT LOOP (a redis.asyncio connection is bound to the loop that
# opened it): a slot poll is not worth a fresh TCP connect and DNS lookup every time.
_CLIENTS: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, Any] = (
    weakref.WeakKeyDictionary()
)
_LOCAL_NEXT: dict[str, float] = {}


class ThrottledError(NonRetryableToolError):
    """No call slot freed up within the wait budget: the upstream is being protected."""


def _client() -> Any:
    loop = asyncio.get_running_loop()
    client = _CLIENTS.get(loop)
    if client is None:
        client = aioredis.from_url(  # type: ignore[no-untyped-call]  # redis async API
            os.environ.get("REDIS_URL", DEFAULT_REDIS_URL), socket_connect_timeout=0.25
        )
        _CLIENTS[loop] = client
    return client


async def _local_slot(name: str, interval_s: float) -> None:
    """Per-process spacing - the fallback when the shared slot cannot be read."""
    now = time.monotonic()
    at = max(now, _LOCAL_NEXT.get(name, 0.0))
    _LOCAL_NEXT[name] = at + interval_s
    if at > now:
        await asyncio.sleep(at - now)


async def acquire_slot(name: str, *, interval_s: float = 1.0, max_wait_s: float = 15.0) -> None:
    """Return when the caller may make ONE call to ``name``.

    Raises ``ThrottledError`` if no slot frees up within ``max_wait_s``.
    """
    key = f"throttle:{name}"
    px = max(1, int(interval_s * 1000))
    deadline = time.monotonic() + max_wait_s
    while True:
        try:
            client = _client()
            if await client.set(key, "1", nx=True, px=px):
                return
            held_ms = await client.pttl(key)
        except Exception:
            record_error("redis_error")
            await _local_slot(name, interval_s)
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ThrottledError(
                f"{name}: no call slot within {max_wait_s:.0f}s - upstream protected"
            )
        # Sleep until the holder's slot expires, plus jitter so waiters do not stampede.
        wait_s = held_ms / 1000 if held_ms and held_ms > 0 else interval_s / 4
        jitter = random.uniform(0.0, 0.05)  # noqa: S311  # nosec B311 - scheduling jitter, not security
        await asyncio.sleep(min(remaining, wait_s + jitter))
