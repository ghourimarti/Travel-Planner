"""S10a: best-effort cache-aside — hit/miss/skip-empty/error/down, no real Redis."""

from __future__ import annotations

import asyncio

import pytest
import tp_core.cache as cache
from pydantic import TypeAdapter

_LIST = TypeAdapter(list[str])


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.sets = 0

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, *, ex=None):
        self.store[key] = value
        self.sets += 1

    async def aclose(self):
        pass


@pytest.fixture
def fake(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr(cache.aioredis, "from_url", lambda *a, **k: redis)
    return redis


def test_miss_then_hit_does_not_recompute(fake):
    calls = {"n": 0}

    async def factory():
        calls["n"] += 1
        return ["a", "b"]

    async def go():
        first = await cache.cache_aside("k", 60, factory, _LIST)
        second = await cache.cache_aside("k", 60, factory, _LIST)
        return first, second

    first, second = asyncio.run(go())
    assert first == ["a", "b"] and second == ["a", "b"]
    assert calls["n"] == 1  # the second call was served from cache


def test_empty_result_not_cached(fake):
    async def factory():
        return []

    asyncio.run(cache.cache_aside("e", 60, factory, _LIST))
    assert fake.sets == 0  # a falsy (transient-failure) result is never stored


def test_factory_error_propagates(fake):
    async def boom():
        raise RuntimeError("tool down")

    with pytest.raises(RuntimeError):
        asyncio.run(cache.cache_aside("x", 60, boom, _LIST))


def test_redis_down_falls_through(monkeypatch):
    class _Down:
        async def get(self, key):
            raise ConnectionError("redis down")

        async def set(self, *a, **k):
            raise ConnectionError("redis down")

        async def aclose(self):
            pass

    monkeypatch.setattr(cache.aioredis, "from_url", lambda *a, **k: _Down())

    async def factory():
        return ["x"]

    assert asyncio.run(cache.cache_aside("k", 60, factory, _LIST)) == ["x"]
