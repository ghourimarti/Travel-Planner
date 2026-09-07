"""Local serving venues: chain parsing, chain order, and the circuit breaker.

These assert BEHAVIOUR that can fail, not merely that symbols exist. The breaker
tests in particular check CALL COUNTS on the fake providers: a breaker that is
"declared but never consulted" would still satisfy a test that only inspected
its own state, which is exactly the declared-but-dead shape this codebase keeps
finding.
"""

from __future__ import annotations

import asyncio

import pytest
from tp_core.exceptions import ConfigError, NonRetryableProviderError, RetryableProviderError
from tp_core.llm.circuit import BreakerState, CircuitBreaker
from tp_core.llm.gateway import LLMGateway
from tp_core.llm.types import LLMResponse, Message, Provider, Tier, Usage
from tp_core.llm.venues import ChainLeg, parse_chain, raw_chain_for_tier

MSGS = [Message(role="user", content="hi")]


class _Fake:
    """A provider double. `model` is set for local venues, mirroring the real one."""

    def __init__(
        self,
        provider: Provider,
        *,
        raise_exc: Exception | None = None,
        model: str | None = None,
    ) -> None:
        self.provider = provider
        self._raise = raise_exc
        self.calls = 0
        if model is not None:
            self.model = model

    async def complete(self, messages, model, tier, *, max_tokens):  # noqa: ANN001, ANN201
        self.calls += 1
        if self._raise is not None:
            raise self._raise
        return LLMResponse(
            text="ok", provider=self.provider, model=model, tier=tier, usage=Usage()
        )


# --------------------------------------------------------------- parse_chain --

def test_parse_chain_order_is_preserved() -> None:
    assert [leg.venue for leg in parse_chain("local-sglang,groq,openai")] == [
        Provider.LOCAL_SGLANG,
        Provider.GROQ,
        Provider.OPENAI,
    ]


def test_bare_local_resolves_through_serving_engine() -> None:
    assert parse_chain("local,groq", default_engine="vllm")[0].venue is Provider.LOCAL_VLLM
    assert parse_chain("local,groq", default_engine="sglang")[0].venue is Provider.LOCAL_SGLANG


@pytest.mark.parametrize("engine", ["sglang", "vllm"])
def test_engine_named_as_a_venue_is_rejected_and_names_the_fix(engine: str) -> None:
    """`sglang,groq` is the easy mistake; the error must say what to write instead."""
    with pytest.raises(ConfigError) as ei:
        parse_chain(f"{engine},groq")
    msg = str(ei.value)
    assert "ENGINE" in msg
    assert f"local-{engine}" in msg  # the actual fix, not just "invalid entry"


def test_unknown_venue_and_duplicates_are_rejected() -> None:
    with pytest.raises(ConfigError):
        parse_chain("groq,bedrock")
    with pytest.raises(ConfigError):
        parse_chain("groq,openai,groq")
    with pytest.raises(ConfigError):
        parse_chain("   ")


# -------------------------------------------------------------- chain wiring --

def test_chain_order_beats_tier_routing_order() -> None:
    """With a chain set, the LOCAL leg answers even though TIER_ROUTING puts OpenAI first."""
    local = _Fake(Provider.LOCAL_SGLANG, model="Qwen/Qwen2.5-7B-Instruct-AWQ")
    openai = _Fake(Provider.OPENAI)
    gw = LLMGateway(
        {Provider.OPENAI: openai, Provider.LOCAL_SGLANG: local},
        chains={Tier.MID: [ChainLeg(Provider.LOCAL_SGLANG), ChainLeg(Provider.OPENAI)]},
    )
    resp = asyncio.run(gw.complete(MSGS, Tier.MID))
    assert resp.provider is Provider.LOCAL_SGLANG
    assert resp.model == "Qwen/Qwen2.5-7B-Instruct-AWQ"  # the LOADED model, not a catalog entry
    assert openai.calls == 0


def test_no_chain_keeps_legacy_tier_routing() -> None:
    """Backward compatibility: chain=None must behave exactly as before."""
    openai = _Fake(Provider.OPENAI)
    gw = LLMGateway({Provider.OPENAI: openai})
    resp = asyncio.run(gw.complete(MSGS, Tier.MID))
    assert resp.provider is Provider.OPENAI
    assert resp.model == "gpt-4o"


def test_local_then_groq_then_openai_failover() -> None:
    """The whole point: local dies -> groq answers; groq dies too -> openai answers."""
    local = _Fake(Provider.LOCAL_SGLANG, model="m", raise_exc=RetryableProviderError("down"))
    groq = _Fake(Provider.GROQ, raise_exc=RetryableProviderError("429"))
    openai = _Fake(Provider.OPENAI)
    gw = LLMGateway(
        {Provider.LOCAL_SGLANG: local, Provider.GROQ: groq, Provider.OPENAI: openai},
        chains={
            Tier.CHEAP: [
                ChainLeg(Provider.LOCAL_SGLANG),
                ChainLeg(Provider.GROQ),
                ChainLeg(Provider.OPENAI),
            ]
        },
    )
    resp = asyncio.run(gw.complete(MSGS, Tier.CHEAP))
    assert resp.provider is Provider.OPENAI
    assert (local.calls, groq.calls, openai.calls) == (1, 1, 1)


def test_leg_without_a_configured_provider_is_skipped_not_an_error() -> None:
    """A chain may name a venue that has no URL/key yet; it is skipped silently."""
    groq = _Fake(Provider.GROQ)
    gw = LLMGateway(
        {Provider.GROQ: groq},
        # LOCAL_VLLM is deliberately NOT configured
        chains={Tier.CHEAP: [ChainLeg(Provider.LOCAL_VLLM), ChainLeg(Provider.GROQ)]},
    )
    resp = asyncio.run(gw.complete(MSGS, Tier.CHEAP))
    assert resp.provider is Provider.GROQ


# ------------------------------------------------------------------ breaker --

def test_breaker_opens_after_threshold_and_the_leg_stops_being_called() -> None:
    """PROVES the skip: the dead leg's call count must STOP rising once open."""
    local = _Fake(Provider.LOCAL_SGLANG, model="m", raise_exc=RetryableProviderError("down"))
    groq = _Fake(Provider.GROQ)
    gw = LLMGateway(
        {Provider.LOCAL_SGLANG: local, Provider.GROQ: groq},
        chains={Tier.CHEAP: [ChainLeg(Provider.LOCAL_SGLANG), ChainLeg(Provider.GROQ)]},
        breaker=CircuitBreaker(threshold=2, cooldown_s=999.0),
    )
    for _ in range(5):
        assert asyncio.run(gw.complete(MSGS, Tier.CHEAP)).provider is Provider.GROQ

    # 2 attempts to trip it, then never again for the cooldown.
    assert local.calls == 2, f"dead leg was retried {local.calls} times; breaker not consulted"
    assert groq.calls == 5


def test_non_retryable_does_not_open_the_breaker() -> None:
    """A 400 is our bad request; it fails identically everywhere, so it must not
    punish the venue."""
    br = CircuitBreaker(threshold=1, cooldown_s=999.0)
    local = _Fake(Provider.LOCAL_SGLANG, model="m", raise_exc=NonRetryableProviderError("400"))
    gw = LLMGateway(
        {Provider.LOCAL_SGLANG: local},
        chains={Tier.CHEAP: [ChainLeg(Provider.LOCAL_SGLANG)]},
        breaker=br,
    )
    with pytest.raises(NonRetryableProviderError):
        asyncio.run(gw.complete(MSGS, Tier.CHEAP))
    assert br.state(Provider.LOCAL_SGLANG) is BreakerState.CLOSED


def test_half_open_admits_exactly_one_probe() -> None:
    br = CircuitBreaker(threshold=1, cooldown_s=10.0)
    br.record_failure(Provider.GROQ, now=0.0)
    assert br.state(Provider.GROQ, now=5.0) is BreakerState.OPEN
    assert br.allows(Provider.GROQ, now=5.0) is False

    # cooldown elapsed -> exactly one caller gets through
    assert br.state(Provider.GROQ, now=20.0) is BreakerState.HALF_OPEN
    assert br.allows(Provider.GROQ, now=20.0) is True
    assert br.allows(Provider.GROQ, now=20.0) is False, "a second probe was admitted"


def test_success_closes_the_breaker() -> None:
    br = CircuitBreaker(threshold=1, cooldown_s=0.0)
    br.record_failure(Provider.GROQ, now=0.0)
    br.record_success(Provider.GROQ)
    assert br.state(Provider.GROQ) is BreakerState.CLOSED
    assert br.allows(Provider.GROQ) is True


def test_snapshot_reports_every_known_leg() -> None:
    """A gauge written only for the leg that moved leaves the others stale."""
    br = CircuitBreaker(threshold=1, cooldown_s=999.0)
    br.record_success(Provider.OPENAI)
    br.record_failure(Provider.LOCAL_SGLANG, now=0.0)
    snap = br.snapshot(now=1.0)  # same clock the failure was recorded on
    assert snap["openai"] == "closed"
    assert snap["local-sglang"] == "open"


# --------------------------------------------------- per-tier chains (D24) --

def test_venue_model_override_grammar() -> None:
    legs = parse_chain("groq:llama-3.3-70b-versatile,openai:gpt-4o")
    assert (legs[0].venue, legs[0].model) == (Provider.GROQ, "llama-3.3-70b-versatile")
    assert (legs[1].venue, legs[1].model) == (Provider.OPENAI, "gpt-4o")


def test_override_model_beats_the_tier_catalog() -> None:
    """`venue:model` must win over TIER_ROUTING's default for that tier."""
    groq = _Fake(Provider.GROQ)
    gw = LLMGateway(
        {Provider.GROQ: groq},
        chains={Tier.CHEAP: [ChainLeg(Provider.GROQ, model="llama-3.3-70b-versatile")]},
    )
    resp = asyncio.run(gw.complete(MSGS, Tier.CHEAP))
    assert resp.model == "llama-3.3-70b-versatile"  # not the CHEAP default 8b-instant


def test_a_tier_without_a_chain_keeps_legacy_order() -> None:
    """Per-tier config is narrow: configuring CHEAP must not touch FRONTIER."""
    openai = _Fake(Provider.OPENAI)
    local = _Fake(Provider.LOCAL_SGLANG, model="qwen")
    gw = LLMGateway(
        {Provider.OPENAI: openai, Provider.LOCAL_SGLANG: local},
        chains={Tier.CHEAP: [ChainLeg(Provider.LOCAL_SGLANG)]},  # FRONTIER unset
    )
    assert asyncio.run(gw.complete(MSGS, Tier.CHEAP)).provider is Provider.LOCAL_SGLANG
    # FRONTIER falls through to the hardcoded table, which is OpenAI-first.
    assert asyncio.run(gw.complete(MSGS, Tier.FRONTIER)).provider is Provider.OPENAI


def test_the_d24_quality_guarantee_local_cheap_hosted_frontier() -> None:
    """THE POINT OF PER-TIER CHAINS.

    A single loaded 7B serves every tier identically, so a global chain would put
    it on FRONTIER too — handing multi-city planning and the critic to a 7B, which
    is exactly where itinerary quality is decided. This asserts the split holds.
    """
    local = _Fake(Provider.LOCAL_SGLANG, model="Qwen/Qwen2.5-7B-Instruct-AWQ")
    openai = _Fake(Provider.OPENAI)
    gw = LLMGateway(
        {Provider.LOCAL_SGLANG: local, Provider.OPENAI: openai},
        chains={
            Tier.CHEAP: [ChainLeg(Provider.LOCAL_SGLANG), ChainLeg(Provider.OPENAI)],
            Tier.FRONTIER: [ChainLeg(Provider.OPENAI)],  # deliberately no local leg
        },
    )
    assert asyncio.run(gw.complete(MSGS, Tier.CHEAP)).provider is Provider.LOCAL_SGLANG
    assert asyncio.run(gw.complete(MSGS, Tier.FRONTIER)).provider is Provider.OPENAI
    assert local.calls == 1, "the 7B was used for FRONTIER; the quality split leaked"


def test_raw_chain_precedence_specific_beats_baseline() -> None:
    per_tier = {Tier.CHEAP: "groq", Tier.MID: "", Tier.FRONTIER: "   "}
    base = "local-sglang,openai"
    assert raw_chain_for_tier(Tier.CHEAP, baseline=base, per_tier=per_tier) == "groq"
    # blank/whitespace override means "not set" -> falls back, never an empty chain
    assert raw_chain_for_tier(Tier.MID, baseline=base, per_tier=per_tier) == base
    assert raw_chain_for_tier(Tier.FRONTIER, baseline=base, per_tier=per_tier) == base


# ------------------------------------------------------- metrics are WRITTEN --

def test_venue_metrics_are_actually_emitted() -> None:
    """Asserts the CALL happened, not the payload.

    A metric that is declared, exported and referenced by a dashboard but never
    incremented scrapes cleanly as 0 or absent — indistinguishable from "nothing
    happened". This test fails if the gateway stops calling the recorder.
    """
    from tp_core import metrics

    seen: list[tuple] = []
    orig_usage, orig_circuit = metrics.record_venue_usage, metrics.record_circuit
    import tp_core.llm.gateway as gw_mod

    gw_mod.record_venue_usage = lambda *a: seen.append(("usage", *a))  # type: ignore[assignment]
    gw_mod.record_circuit = lambda s: seen.append(("circuit", tuple(sorted(s.items()))))  # type: ignore[assignment]
    try:
        gw = LLMGateway(
            {Provider.LOCAL_SGLANG: _Fake(Provider.LOCAL_SGLANG, model="qwen")},
            chains={Tier.CHEAP: [ChainLeg(Provider.LOCAL_SGLANG)]},
        )
        asyncio.run(gw.complete(MSGS, Tier.CHEAP))
    finally:
        gw_mod.record_venue_usage = orig_usage  # type: ignore[assignment]
        gw_mod.record_circuit = orig_circuit  # type: ignore[assignment]

    kinds = [s[0] for s in seen]
    assert "usage" in kinds, "venue usage was never recorded"
    assert "circuit" in kinds, "breaker state was never published"
    usage = next(s for s in seen if s[0] == "usage")
    assert usage[1] == "local-sglang"  # attributed to the venue that served


# ------------------------------------------- venue reaches the API contract --

def test_venue_survives_serialization_into_the_run_result() -> None:
    """`mark_succeeded` stores `result.model_dump(mode="json")`, and RunRecord
    serves that dict straight to the API. If `venues` does not survive the dump,
    "which venue answered?" stays a log-only question."""
    from tp_agents.schemas import Itinerary

    it = Itinerary(
        city="Kyoto",
        summary_markdown="x",
        venues=["local-sglang", "openai"],
        cost_usd=0.0,
    )
    dumped = it.model_dump(mode="json")
    assert dumped["venues"] == ["local-sglang", "openai"]
    # cost 0.0 must serialize too — absent and zero are different answers.
    assert dumped["cost_usd"] == 0.0


def test_trip_unions_venues_across_cities() -> None:
    from tp_agents.schemas import Itinerary, TripItinerary

    a = Itinerary(city="Kyoto", summary_markdown="", venues=["local-sglang"])
    b = Itinerary(city="Osaka", summary_markdown="", venues=["groq", "local-sglang"])
    trip = TripItinerary(
        summary_markdown="",
        cities=[a, b],
        venues=sorted({v for c in (a, b) for v in c.venues}),
    )
    assert trip.venues == ["groq", "local-sglang"]  # deduped, deterministic order
