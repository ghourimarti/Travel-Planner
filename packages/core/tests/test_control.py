"""The kill switch reads Redis fail-open."""

from __future__ import annotations

import asyncio

import tp_core.control as control


def test_planning_enabled_fails_open():
    # conftest patches from_url to raise -> a Redis blip leaves planning enabled
    assert asyncio.run(control.planning_enabled()) is True


def test_planning_disabled_when_flag_set(monkeypatch):
    class _R:
        async def get(self, key):
            return b"0"

        async def aclose(self):
            pass

    monkeypatch.setattr(control.aioredis, "from_url", lambda *a, **k: _R())
    assert asyncio.run(control.planning_enabled()) is False
