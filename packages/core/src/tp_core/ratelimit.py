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

**Fail-open**: any Redis error means allow — availability over strictness, the same
posture as the kill switch — so a Redis outage never becomes a service outage. The
trade is explicit: an attacker who can take Redis down can also lift the limits, which
is acceptable only because the spend breaker in ``control.py`` still applies.

A limit of 0 disables that check entirely. That is how every new limit ships, so
adding this module cannot start refusing traffic on an existing deployment.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from tp_core.logging import get_logger
from tp_core.settings import DEFAULT_REDIS_URL, get_settings

_log = get_logger("tp_core.ratelimit")

WINDOW_MINUTE = 60
WINDOW_DAY = 24 * 3600


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
    except Exception:  # fail-open: never block legit traffic on a Redis blip
        _log.warning("ratelimit_unavailable", identity=identity, scope=scope)
        return True
    return count is None or count <= limit


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
