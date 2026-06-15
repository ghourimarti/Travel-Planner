"""S12d: per-tenant fixed-window rate limiting — threshold + fail-open, no real Redis."""

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
