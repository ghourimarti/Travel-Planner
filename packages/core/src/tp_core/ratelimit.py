"""Rate limiting: Redis fixed-window counters, per scope and per window.

TWO SCOPES, BECAUSE ONE IS DEFEATABLE
-------------------------------------
A per-TENANT limit is defeated by minting tenants: rotate the session cookie and the
allowance multiplies by however many cookies the caller cares to mint. A per-IP limit
closes that, at the cost of over-counting users behind shared NAT. Neither is
sufficient alone, so both are checked and the strictest wins.

TWO WINDOWS, BECAUSE A MINUTE IS NOT A BUDGET
---------------------------------------------
A per-minute limit bounds burst; it does nothing about a caller who sits exactly under
it all day. The daily window is the actual budget.

**Fail-open - to a LOCAL limit, not to no limit.** A Redis error never becomes a
service outage (availability over strictness, the kill switch's posture), but the same
window is then counted in-process. "Allow everything" was the old reading of fail-open,
and under load it AMPLIFIED: connects to Redis failed during a DNS storm, every failure
admitted the request, and 159 plans got in against a limit of 60 - feeding the very load
that broke the connects (2026-09-30). Per-process counting keeps legitimate traffic
flowing and still refuses a flood; with N API replicas the ceiling is N x the limit.

A limit of 0 disables that check entirely. That is how every new limit ships, so
adding this module cannot start refusing traffic on an existing deployment.
"""

from __future__ import annotations

import asyncio
import os
import time
import weakref
from typing import Any

import redis.asyncio as aioredis

from tp_core.logging import get_logger
from tp_core.metrics import record_error
from tp_core.settings import DEFAULT_REDIS_URL, get_settings

_log = get_logger("tp_core.ratelimit")

WINDOW_MINUTE = 60
WINDOW_DAY = 24 * 3600

# One pooled client per EVENT LOOP. Opening a connection per check meant a TCP connect
# and a DNS lookup of `redis` on every request - the lookups are what failed under load.
_CLIENTS: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, Any] = (
    weakref.WeakKeyDictionary()
)

# The in-process fallback windows: key -> (window started at, count, window length).
_LOCAL: dict[str, tuple[float, int, int]] = {}
_LOCAL_MAX_KEYS = 10_000


def _redis_url() -> str:
    try:
        return str(getattr(get_settings(), "redis_url", DEFAULT_REDIS_URL))
    except Exception:  # settings incomplete (e.g. no provider key): the env var still names Redis
        return os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)


def _client() -> Any:
    loop = asyncio.get_running_loop()
    client = _CLIENTS.get(loop)
    if client is None:
        client = aioredis.from_url(  # type: ignore[no-untyped-call]
            _redis_url(), socket_connect_timeout=0.25
        )
        _CLIENTS[loop] = client
    return client


async def _incr_window(key: str, window_s: int) -> int:
    """Increment the shared window counter and return the new count (raises if Redis fails)."""
    client = _client()
    count = await client.incr(key)
    if count == 1:  # first hit in this window — set the TTL once
        await client.expire(key, window_s)
    return int(count)


def _local_incr(key: str, window_s: int) -> int:
    """The same fixed window, counted in this process - used only while Redis is unreachable."""
    now = time.monotonic()
    if len(_LOCAL) > _LOCAL_MAX_KEYS:  # bound memory: forget windows that have ended
        for stale in [k for k, (t0, _, w) in _LOCAL.items() if now - t0 >= w]:
            del _LOCAL[stale]
    started, count, _ = _LOCAL.get(key, (now, 0, window_s))
    if now - started >= window_s:
        started, count = now, 0
    _LOCAL[key] = (started, count + 1, window_s)
    return count + 1


async def allow_request(
    identity: str,
    *,
    limit: int,
    window_s: int = WINDOW_MINUTE,
    scope: str = "tenant",
) -> bool:
    """Whether ``identity`` is under its budget for the current window.

    ``scope`` namespaces the counter. Without it a tenant id and an IP that happened
    to be the same string would share one counter — unlikely, but the kind of
    collision that is impossible to diagnose from a 429.
    """
    if limit <= 0:  # 0/negative disables limiting
        return True
    window = f"ratelimit:{scope}:{identity}:{window_s}"
    try:
        count = await _incr_window(window, window_s)
    except Exception:  # fail-open to the LOCAL window - never block legit traffic on a blip
        # COUNTED, not just logged. A 9-minute Redis outage used to leave no trace in
        # tp_errors_total at all - every limiter lifted silently, visible only in logs.
        record_error("redis_error")
        _log.warning("ratelimit_unavailable", identity=identity, scope=scope)
        count = _local_incr(window, window_s)
    return count <= limit


def client_ip(forwarded_for: str | None, peer: str | None, hops: int) -> str | None:
    """The caller's address, honouring exactly ``hops`` trusted proxies.

    ``hops <= 0`` IGNORES ``X-Forwarded-For`` entirely and returns the socket peer.
    That is the safe default and the reason it ships as 0: a header you trust but
    nobody sets is a header anyone can forge, and the per-IP limit would then be
    defeated by one line of curl while still looking enforced on the dashboard.

    With ``hops = N`` the client is the Nth entry from the RIGHT, because each proxy
    APPENDS the address it saw. Counting from the left instead takes whatever the
    caller put there, which is attacker-controlled.
    """
    if hops <= 0 or not forwarded_for:
        return peer
    parts = [p.strip() for p in forwarded_for.split(",") if p.strip()]
    if not parts:
        return peer
    idx = max(len(parts) - hops, 0)
    return parts[idx]
