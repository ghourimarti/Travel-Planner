"""Per-tenant rate limiting (S12d): a Redis fixed-window counter.

One key per tenant per window (``INCR`` then ``EXPIRE`` on first hit). **Fail-open**:
any Redis error means allow — availability over strictness, the same posture as the
S10b kill switch — so a Redis outage never turns into a service outage.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from tp_core.logging import get_logger
from tp_core.settings import DEFAULT_REDIS_URL, get_settings

_log = get_logger("tp_core.ratelimit")


async def _incr_window(key: str, window_s: int) -> int | None:
    """Increment the window counter and return the new count, or ``None`` on any failure."""
    redis_url = getattr(get_settings(), "redis_url", DEFAULT_REDIS_URL)
    client = aioredis.from_url(  # type: ignore[no-untyped-call]
        redis_url, socket_connect_timeout=0.25
    )
    try:
        count = await client.incr(key)
        if count == 1:  # first hit in this window — set the TTL once
            await client.expire(key, window_s)
        return int(count)
    finally:
        await client.aclose()


async def allow_request(tenant_id: str, *, limit: int, window_s: int = 60) -> bool:
    """Whether ``tenant_id`` is under its request budget for the current window."""
    if limit <= 0:  # 0/negative disables limiting
        return True
    window = f"ratelimit:{tenant_id}:{window_s}"
    try:
        count = await _incr_window(window, window_s)
    except Exception:  # fail-open: never block legit traffic on a Redis blip
        _log.warning("ratelimit_unavailable", tenant_id=tenant_id)
        return True
    return count is None or count <= limit
