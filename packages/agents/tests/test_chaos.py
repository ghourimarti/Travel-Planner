"""Chaos tests: prove the degradation matrix holds under dependency failure.

Each test kills a dependency and asserts the system *degrades* — a warning + a thinner
result or a typed error — instead of crashing or hanging. Run with ``pytest -m chaos``.
Hermetic: no network, no keys, no Redis (the root conftest no-ops the cache).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
import tp_agents.nodes as nodes
from tp_agents import PlanRequest, plan
from tp_core.exceptions import ProviderError, RetryableProviderError, ToolError
from tp_core.llm import LLMGateway, LLMResponse, Provider, Tier, Usage

_GEO = nodes.GeoLocation(name="Tokyo", latitude=35.68, longitude=139.69, country="Japan")
_POIS = [nodes.POI(name="Senso-ji", category="temples", latitude=35.71, longitude=139.79)]


class _FakeProvider:
    """A provider that always answers (stands in for a healthy LLM)."""

    async def complete(self, messages: Any, model: str, tier: Tier, *, max_tokens: int = 1024):
        return LLMResponse(
            text="Day 1: explore.",
            provider=Provider.OPENAI,
            model=model,
            tier=tier,
            usage=Usage(input_tokens=10, output_tokens=10, cost_usd=0.0001),
        )


class _DeadProvider:
    """A provider that is always down (transient error on every call)."""

    async def complete(self, messages: Any, model: str, tier: Tier, *, max_tokens: int = 1024):
        raise RetryableProviderError("upstream 503")


@pytest.mark.chaos
def test_geocode_outage_degrades_without_llm_spend(monkeypatch):
    """Geocode down -> ungrounded 'not found' itinerary + warning; compose skips the LLM."""

    async def boom(city: str):
        raise ToolError("nominatim unreachable")

    monkeypatch.setattr(nodes, "geocode", boom)

    class _NeverCalled:
        async def complete(self, *a: Any, **k: Any):
            raise AssertionError("LLM must not be called when the city can't be resolved")

    gateway = LLMGateway({Provider.OPENAI: _NeverCalled()})
    itin = asyncio.run(plan(PlanRequest(city="Tokyo", interests=["temples"]), gateway=gateway))
    assert itin.grounded is False
    assert itin.warnings  # honest about the failure


@pytest.mark.chaos
def test_all_llm_providers_down_raise_typed_error():
    """Every provider down -> a single typed ProviderError, not an arbitrary crash."""
    gateway = LLMGateway({Provider.OPENAI: _DeadProvider()})
    with pytest.raises(ProviderError):
        asyncio.run(gateway.complete([], Tier.MID))


@pytest.mark.chaos
def test_retriever_outage_falls_back_to_live_pois(monkeypatch):
    """Corpus (Qdrant) down -> warning + fall back to live POI tools, still produce an itinerary."""

    async def geocode(city: str):
        return _GEO

    async def find_pois(lat: float, lon: float, interest: str, **kw: Any):
        return list(_POIS)

    async def forecast(lat: float, lon: float, *, days: int = 3):
        return []

    monkeypatch.setattr(nodes, "geocode", geocode)
    monkeypatch.setattr(nodes, "find_pois", find_pois)
    monkeypatch.setattr(nodes, "forecast", forecast)

    class _DeadRetriever:
        async def retrieve(self, city: str, interests: list[str], *, tenant_id: str | None = None):
            raise RuntimeError("qdrant connection refused")

    itin = asyncio.run(
        plan(
            PlanRequest(city="Tokyo", interests=["temples"]),
            gateway=LLMGateway({Provider.OPENAI: _FakeProvider()}),
            retriever=_DeadRetriever(),
        )
    )
    assert any("retrieval failed" in w.lower() for w in itin.warnings)
    assert itin.pois_used  # live-tool fallback supplied POIs
