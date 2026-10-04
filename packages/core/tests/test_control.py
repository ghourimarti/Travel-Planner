"""The kill switch reads Redis fail-open."""

from __future__ import annotations

import asyncio

import tp_core.control as control


def test_planning_enabled_fails_open():
    # conftest patches from_url to raise -> a Redis blip leaves planning enabled
    assert asyncio.run(control.planning_enabled()) is True


def test_redis_failure_on_the_kill_switch_is_counted():
    """Still fail-open - but `suppress(Exception)` used to make the outage invisible."""
    from prometheus_client import REGISTRY

    def redis_errors() -> float:
        return REGISTRY.get_sample_value("tp_errors_total", {"type": "redis_error"}) or 0.0

    before = redis_errors()
    assert asyncio.run(control.planning_enabled()) is True
    assert redis_errors() >= before + 1


def test_planning_disabled_when_flag_set(monkeypatch):
    class _R:
        async def get(self, key):
            return b"0"

        async def aclose(self):
            pass

    monkeypatch.setattr(control.aioredis, "from_url", lambda *a, **k: _R())
    assert asyncio.run(control.planning_enabled()) is False


# --- per-run spend tally (2026-10-01) -----------------------------------------------------

def test_run_spend_is_tallied_even_when_redis_is_down(monkeypatch):
    """A run's own cost must not depend on the ledger being reachable."""
    monkeypatch.setattr(control, "_redis_allowed", lambda: False)

    async def one_run() -> float:
        tally = control.track_run_spend()
        await control.record_spend(0.001)
        await control.record_spend(0.0)  # a free local call is recorded as zero
        await control.record_spend(-1.0)  # never negative
        # Work the run spawns (LangGraph branches, gather) shares the run's tally.
        await asyncio.gather(control.record_spend(0.0002), control.record_spend(0.0003))
        return tally[0]

    assert round(asyncio.run(one_run()), 9) == 0.0015


def test_spend_outside_a_run_touches_no_tally(monkeypatch):
    """The API, the eval CLI and the tests record exactly as before: no run, no tally."""
    monkeypatch.setattr(control, "_redis_allowed", lambda: False)

    async def no_run() -> object:
        await control.record_spend(0.5)
        return control._RUN_SPEND.get()

    assert asyncio.run(no_run()) is None
