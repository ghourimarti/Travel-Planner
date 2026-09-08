"""The daily spend breaker, tested WITHOUT mocking the thing under test.

WHY THIS FILE EXISTS
--------------------
The breaker shipped dead. `record_spend()` was written, `spend_today()` read the key it
writes, `spend_state()` compared that against the limit, and `planning_enabled()`
consulted `spend_state()` — every piece correct, and the whole thing inert, because
NOTHING EVER CALLED `record_spend()`. Spend was always 0.0, so
`DAILY_SPEND_LIMIT_USD` could never trip.

The original tests passed. They monkeypatched `spend_today` to return a number, which
tests the arithmetic *below* the bug and can never see it. A control that is only ever
exercised through a mock of its own input is a control nobody has tested.

So these tests do two things the old ones did not:

1. **Round-trip through a real store.** `record_spend()` WRITES and `spend_today()`
   READS, with no patching in between — only a fake Redis that genuinely stores.
2. **Assert the GATEWAY calls it.** That is where the bug actually was. A control.py
   test, however thorough, would have stayed green.
"""

from __future__ import annotations

import asyncio

import pytest
import tp_core.control as control
from tp_core.llm.circuit import reset_infra_breakers
from tp_core.llm.gateway import LLMGateway
from tp_core.llm.types import LLMResponse, Message, Provider, Tier, Usage
from tp_core.llm.venues import ChainLeg

MSGS = [Message(role="user", content="hi")]


class _FakeRedis:
    """A Redis that actually stores, so a write can be read back."""

    def __init__(self) -> None:
        self.store: dict[str, float] = {}
        self.expires: dict[str, int] = {}

    async def incrbyfloat(self, key: str, amount: float) -> float:
        self.store[key] = self.store.get(key, 0.0) + float(amount)
        return self.store[key]

    async def expire(self, key: str, ttl: int) -> bool:
        self.expires[key] = ttl
        return True

    async def get(self, key: str):  # noqa: ANN201
        v = self.store.get(key)
        return None if v is None else str(v).encode()

    async def aclose(self) -> None:
        return None


@pytest.fixture
def redis(monkeypatch):
    reset_infra_breakers()
    fake = _FakeRedis()
    monkeypatch.setattr(control.aioredis, "from_url", lambda *a, **k: fake)
    return fake


# ------------------------------------------------- 1. a real write, a real read
def test_spend_round_trips_without_any_mocking_of_spend_today(redis):
    """The check the original tests could not make: does a write survive to a read?"""
    assert asyncio.run(control.spend_today()) == 0.0
    asyncio.run(control.record_spend(0.25))
    asyncio.run(control.record_spend(0.10))
    assert asyncio.run(control.spend_today()) == pytest.approx(0.35)


def test_zero_is_recorded_not_skipped(redis):
    """A self-hosted day must read ZERO, not absent. They mean different things."""
    asyncio.run(control.record_spend(0.0))
    assert redis.store, "a $0 call must still create the key"
    assert asyncio.run(control.spend_today()) == 0.0


def test_the_key_carries_a_ttl(redis):
    """The key expires itself. A cost control that needs a cleanup job to keep working
    is a cost control with a second thing that can silently break."""
    asyncio.run(control.record_spend(0.01))
    assert redis.expires, "spend key was written with no TTL"


def test_breaker_trips_on_ACCUMULATED_spend(redis, monkeypatch):
    """End to end, no mocks: several small charges cross a limit none of them reach."""
    monkeypatch.setenv("DAILY_SPEND_LIMIT_USD", "1.0")
    for _ in range(9):
        asyncio.run(control.record_spend(0.10))
    assert asyncio.run(control.spend_state()) == "soft_alert"  # 0.90 of 1.00, ratio 0.8
    assert asyncio.run(control.planning_enabled()) is True

    asyncio.run(control.record_spend(0.20))  # -> 1.10, over the limit
    assert asyncio.run(control.spend_state()) == "breached"
    assert asyncio.run(control.planning_enabled()) is False


# ------------------------------------- 2. the test that would have caught the bug
class _FakeProvider:
    def __init__(self, provider: Provider, cost: float, model: str | None = None) -> None:
        self.provider = provider
        self._cost = cost
        # A LOCAL venue has no catalog entry, so `model_for()` returns None and the
        # gateway SKIPS the leg unless the adapter itself reports a loaded model.
        # Omitting this is why the first version of the zero-cost test saw an empty
        # chain rather than a free call.
        if model is not None:
            self.model = model

    async def complete(self, messages, model, tier, *, max_tokens):  # noqa: ANN001, ANN201
        return LLMResponse(
            text="ok",
            provider=self.provider,
            model=model,
            tier=tier,
            usage=Usage(input_tokens=100, output_tokens=10, cost_usd=self._cost),
        )


def test_gateway_records_spend_for_the_venue_that_served(redis):
    """THE REGRESSION TEST FOR THE ACTUAL BUG.

    Everything in control.py was correct; the gateway simply never called it. Any test
    confined to control.py stays green against that. This one drives a real
    `LLMGateway.complete()` and asserts the spend landed.
    """
    gw = LLMGateway({Provider.OPENAI: _FakeProvider(Provider.OPENAI, 0.42)})
    resp = asyncio.run(gw.complete(MSGS, Tier.MID))
    assert resp.provider is Provider.OPENAI
    assert asyncio.run(control.spend_today()) == pytest.approx(0.42), (
        "gateway completed a call but recorded no spend — the breaker is dead again"
    )


def test_gateway_records_zero_cost_calls_too(redis):
    """A local engine costs $0. It must still be RECORDED, so the dashboard can tell
    'served for free' apart from 'served by nothing'."""
    # LOCAL_SGLANG is not in the default MID routing, so the chain must name it.
    gw = LLMGateway(
        {Provider.LOCAL_SGLANG: _FakeProvider(Provider.LOCAL_SGLANG, 0.0, model="Qwen-test")},
        chains={Tier.MID: [ChainLeg(Provider.LOCAL_SGLANG)]},
    )
    asyncio.run(gw.complete(MSGS, Tier.MID))
    assert redis.store, "a free call recorded nothing at all"


def test_spend_recording_never_breaks_a_request(monkeypatch):
    """Best-effort: a dead Redis must not fail the LLM call that triggered it."""
    reset_infra_breakers()
    monkeypatch.setattr(
        control.aioredis, "from_url", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
    )
    gw = LLMGateway({Provider.OPENAI: _FakeProvider(Provider.OPENAI, 0.42)})
    resp = asyncio.run(gw.complete(MSGS, Tier.MID))
    assert resp.text == "ok"
