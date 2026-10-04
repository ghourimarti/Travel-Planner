"""Per-tenant fixed-window rate limiting — threshold + fail-open, no real Redis."""

from __future__ import annotations

import asyncio

from tp_core import ratelimit


def _allow(tenant: str, limit: int) -> bool:
    return asyncio.run(ratelimit.allow_request(tenant, limit=limit))


def test_allows_under_limit(monkeypatch):
    async def fake_incr(key, window_s):
        return 3

    monkeypatch.setattr(ratelimit, "_incr_window", fake_incr)
    assert _allow("acme", 5) is True


def test_blocks_over_limit(monkeypatch):
    async def fake_incr(key, window_s):
        return 6

    monkeypatch.setattr(ratelimit, "_incr_window", fake_incr)
    assert _allow("acme", 5) is False


def test_fails_open_when_backend_errors(monkeypatch):
    async def boom(key, window_s):
        raise ConnectionError("redis down")

    monkeypatch.setattr(ratelimit, "_incr_window", boom)
    assert _allow("acme", 5) is True  # availability over strictness


def test_zero_limit_disables():
    assert _allow("acme", 0) is True


def test_redis_failure_is_counted_not_just_logged(monkeypatch):
    """Fail-open used to be SILENT: a 9-minute Redis outage left tp_errors_total empty."""
    from prometheus_client import REGISTRY

    def redis_errors() -> float:
        return REGISTRY.get_sample_value("tp_errors_total", {"type": "redis_error"}) or 0.0

    async def boom(key, window_s):
        raise ConnectionError("Error 111 connecting to redis:6379. Connection refused.")

    monkeypatch.setattr(ratelimit, "_incr_window", boom)
    before = redis_errors()
    assert _allow("acme", 5) is True  # still fail-open...
    assert redis_errors() == before + 1  # ...but now it leaves a trace


def test_redis_down_still_refuses_a_flood(monkeypatch):
    """Fail-open used to mean NO limit: under load 159 got in against 60 (2026-09-30)."""

    async def boom(key, window_s):
        raise ConnectionError("Temporary failure in name resolution")

    monkeypatch.setattr(ratelimit, "_incr_window", boom)
    results = [_allow("flood-tenant", 3) for _ in range(5)]
    assert results == [True, True, True, False, False]  # the same window, counted locally


def test_one_pooled_client_per_event_loop(monkeypatch):
    """Not a TCP connect + DNS lookup per check - those lookups are what failed under load."""
    made = []

    class _Redis:
        async def incr(self, key):
            return 1

        async def expire(self, key, seconds):
            return True

    def from_url(*args, **kwargs):
        made.append(1)
        return _Redis()

    monkeypatch.setattr(ratelimit.aioredis, "from_url", from_url)

    async def go():
        for _ in range(5):
            assert await ratelimit.allow_request("pool-tenant", limit=10)

    asyncio.run(go())
    assert len(made) == 1
