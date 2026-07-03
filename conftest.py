"""Global test isolation.

Make the best-effort cache (S10a) an instant no-op so the suite is deterministic and
fast regardless of any local Redis (e.g. left running from ``make services``): the
patched ``from_url`` raises, ``cache_aside`` suppresses it, and the factory runs.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_cache(monkeypatch):
    import tp_core.cache

    def _down(*args, **kwargs):
        raise ConnectionError("cache disabled in tests")

    monkeypatch.setattr(tp_core.cache.aioredis, "from_url", _down)

