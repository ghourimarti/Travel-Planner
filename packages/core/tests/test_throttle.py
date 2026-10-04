"""App-wide call spacing for a rate-limited upstream (tp_core.throttle) - no real Redis."""

from __future__ import annotations

import asyncio
import time

import pytest
import tp_core.throttle as throttle
from prometheus_client import REGISTRY


class _SlotRedis:
    """SET NX PX + PTTL, with real expiry against the monotonic clock."""

    def __init__(self) -> None:
        self.expires: dict[str, float] = {}

    async def set(self, key: str, value: str, *, nx: bool = False, px: int = 0) -> bool:
        now = time.monotonic()
        if nx and self.expires.get(key, 0.0) > now:
            return False
        self.expires[key] = now + px / 1000
        return True

    async def pttl(self, key: str) -> int:
        left = self.expires.get(key, 0.0) - time.monotonic()
        return int(left * 1000) if left > 0 else -2


def test_second_caller_waits_for_the_shared_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = _SlotRedis()
    monkeypatch.setattr(throttle, "_client", lambda: redis)

    async def go() -> float:
        await throttle.acquire_slot("t-shared", interval_s=0.2)
        started = time.monotonic()
        await throttle.acquire_slot("t-shared", interval_s=0.2)
        return time.monotonic() - started

    assert asyncio.run(go()) >= 0.15  # the one-call-per-interval rule held


def test_no_slot_within_budget_raises_throttled(monkeypatch: pytest.MonkeyPatch) -> None:
    class _AlwaysHeld(_SlotRedis):
        async def set(self, key: str, value: str, *, nx: bool = False, px: int = 0) -> bool:
            return False

        async def pttl(self, key: str) -> int:
            return 50

    monkeypatch.setattr(throttle, "_client", lambda: _AlwaysHeld())
    with pytest.raises(throttle.ThrottledError):
        asyncio.run(throttle.acquire_slot("t-busy", interval_s=1.0, max_wait_s=0.2))


def test_redis_down_falls_back_to_per_process_spacing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _down() -> object:
        raise ConnectionError("redis down")

    monkeypatch.setattr(throttle, "_client", _down)

    def redis_errors() -> float:
        return REGISTRY.get_sample_value("tp_errors_total", {"type": "redis_error"}) or 0.0

    before = redis_errors()

    async def go() -> float:
        await throttle.acquire_slot("t-local", interval_s=0.2)
        started = time.monotonic()
        await throttle.acquire_slot("t-local", interval_s=0.2)
        return time.monotonic() - started

    assert asyncio.run(go()) >= 0.15  # fail-open for availability, but never unthrottled
    assert redis_errors() >= before + 2  # and the degraded path is counted
