"""Cost controls, rate-limit scopes, cache versioning and infra breakers.

Each test pins a PROPERTY that would otherwise regress silently, because every one of
these features fails quietly by design: a broken kill switch still returns 200s, a
defeated rate limit still shows green, and a cache that never invalidates still serves.
"""

from __future__ import annotations

import asyncio

import pytest
import tp_core.control as control
from tp_core.cache import cache_version
from tp_core.llm.circuit import BreakerState, infra_breaker, reset_infra_breakers
from tp_core.ratelimit import client_ip


# --------------------------------------------------------------- the floor
def test_llm_enabled_floor_beats_a_redis_flag_that_says_enabled(monkeypatch):
    """The static floor must outrank the runtime switch, not merely agree with it."""

    class _R:
        async def get(self, key):
            return b"1"  # Redis says ENABLED

        async def aclose(self):
            pass

    monkeypatch.setattr(control.aioredis, "from_url", lambda *a, **k: _R())
    monkeypatch.setenv("LLM_ENABLED", "false")
    assert asyncio.run(control.planning_enabled()) is False


def test_floor_does_not_need_redis_at_all(monkeypatch):
    """A cost control that stops working when infra is down is worse than none."""
    monkeypatch.setattr(
        control.aioredis, "from_url", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
    )
    monkeypatch.setenv("LLM_ENABLED", "0")
    assert asyncio.run(control.planning_enabled()) is False


# -------------------------------------------------------- the spend breaker
@pytest.mark.parametrize(
    ("limit", "spent", "expected"),
    [
        ("0", 100.0, "ok"),  # 0 disables the breaker entirely — the shipped default
        ("10", 1.0, "ok"),
        ("10", 8.5, "soft_alert"),  # default ratio 0.8
        ("10", 10.0, "breached"),  # at the limit, not merely past it
        ("10", 99.0, "breached"),
    ],
)
def test_spend_state_thresholds(monkeypatch, limit, spent, expected):
    monkeypatch.setenv("DAILY_SPEND_LIMIT_USD", limit)
    monkeypatch.setattr(control, "spend_today", lambda: _async(spent))
    assert asyncio.run(control.spend_state()) == expected


def test_breached_spend_disables_planning(monkeypatch):
    monkeypatch.setenv("DAILY_SPEND_LIMIT_USD", "1")
    monkeypatch.setattr(control, "spend_today", lambda: _async(5.0))
    monkeypatch.setattr(
        control.aioredis, "from_url", lambda *a, **k: (_ for _ in ()).throw(RuntimeError())
    )
    assert asyncio.run(control.planning_enabled()) is False


def test_spend_limit_unset_leaves_planning_enabled(monkeypatch):
    """Adding this module must not start refusing traffic on an existing deployment."""
    monkeypatch.setattr(
        control.aioredis, "from_url", lambda *a, **k: (_ for _ in ()).throw(RuntimeError())
    )
    assert asyncio.run(control.planning_enabled()) is True


async def _async(value):
    return value


# ------------------------------------------------------------ client IP / XFF
def test_forged_forwarded_for_is_ignored_when_no_proxy_is_trusted():
    """The whole point of defaulting to 0 hops: the header is attacker-controlled."""
    assert client_ip("1.2.3.4", "10.0.0.9", hops=0) == "10.0.0.9"


def test_one_trusted_hop_takes_the_rightmost_entry():
    # Each proxy APPENDS what it saw, so the trustworthy end is the RIGHT one.
    assert client_ip("evil, 203.0.113.7", "10.0.0.9", hops=1) == "203.0.113.7"


def test_two_trusted_hops_walk_further_left():
    assert client_ip("client, p1, p2", "10.0.0.9", hops=2) == "p1"


def test_more_hops_than_entries_cannot_index_out_of_range():
    assert client_ip("only-one", "10.0.0.9", hops=5) == "only-one"


def test_missing_header_falls_back_to_the_socket_peer():
    assert client_ip(None, "10.0.0.9", hops=3) == "10.0.0.9"


# ------------------------------------------------------------ cache versioning
def test_cache_version_composes_all_three_parts(monkeypatch):
    monkeypatch.setenv("PROMPT_VERSION", "p9")
    monkeypatch.setenv("CORPUS_VERSION", "c2")
    monkeypatch.setenv("INDEX_VERSION", "i7")
    assert cache_version() == "p9.c2.i7"


def test_bumping_one_version_changes_the_key(monkeypatch):
    monkeypatch.setenv("PROMPT_VERSION", "v1")
    before = cache_version()
    monkeypatch.setenv("PROMPT_VERSION", "v2")
    assert cache_version() != before


# ------------------------------------------------------------- infra breakers
def test_infra_breaker_is_shared_per_name():
    reset_infra_breakers()
    assert infra_breaker("redis") is infra_breaker("redis")
    assert infra_breaker("redis") is not infra_breaker("postgres")


def test_infra_breaker_opens_then_admits_one_probe(monkeypatch):
    reset_infra_breakers()
    monkeypatch.setenv("REDIS_CIRCUIT_FAILURE_THRESHOLD", "2")
    monkeypatch.setenv("REDIS_CIRCUIT_COOLDOWN_SECONDS", "30")
    b = infra_breaker("redis")

    b.record_failure("redis", now=0.0)
    assert b.state("redis", now=0.0) is BreakerState.CLOSED
    b.record_failure("redis", now=0.0)
    assert b.state("redis", now=0.0) is BreakerState.OPEN
    assert b.allows("redis", now=0.0) is False

    # cooldown elapsed -> exactly ONE probe, then closed again on success
    assert b.allows("redis", now=31.0) is True
    assert b.allows("redis", now=31.0) is False
    b.record_success("redis")
    assert b.state("redis", now=31.0) is BreakerState.CLOSED


def test_reset_clears_state_between_tests():
    reset_infra_breakers()
    infra_breaker("redis").record_failure("redis", now=0.0)
    reset_infra_breakers()
    assert infra_breaker("redis").snapshot() == {}


# ------------------------------------------------------ postgres breaker (R2.2)
def test_open_postgres_breaker_raises_rather_than_degrading(monkeypatch):
    """The failure mode this guards against is SILENT history loss.

    "Degrading gracefully" here would mean returning without persisting — so
    create_run hands back a run id that does not exist, and mark_succeeded drops a
    finished itinerary. A caller cannot tell either from success. Raising is the
    correct behaviour, not a limitation.
    """
    import tp_core.db as db

    reset_infra_breakers()
    monkeypatch.setenv("POSTGRES_CIRCUIT_FAILURE_THRESHOLD", "2")
    b = infra_breaker("postgres")
    # NO injected clock here, deliberately. session_scope() calls allows() with the
    # REAL monotonic clock, so opening the breaker at an injected now=0.0 makes the
    # cooldown look long expired and admits a probe — the breaker would read
    # half-open and the test would see no exception. Mixing an injected clock with a
    # real one is the same trap that produced a reporting bug in snapshot().
    b.record_failure("postgres")
    b.record_failure("postgres")
    assert b.state("postgres") is BreakerState.OPEN

    async def _use():
        async with db.session_scope():
            pass  # pragma: no cover - must never be reached

    with pytest.raises(Exception) as exc:
        asyncio.run(_use())
    assert "circuit is OPEN" in str(exc.value)


def test_closed_postgres_breaker_does_not_block(monkeypatch):
    """Default state must be a no-op: adding a breaker cannot break a working app."""
    import tp_core.db as db

    reset_infra_breakers()
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    async def _use():
        async with db.session_scope() as s:
            return s is not None

    assert asyncio.run(_use()) is True
    assert infra_breaker("postgres").state("postgres") is BreakerState.CLOSED
