"""S11a: a planner run emits a nested OTel trace (run -> nodes -> llm), hermetically.

The gateway wraps a fake PROVIDER (not a fake gateway), so the real gateway code path —
and its ``llm.complete`` span — is exercised without a network call or key.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
import tp_agents.nodes as nodes
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from tp_agents import PlanRequest, plan
from tp_core.llm import LLMGateway, LLMResponse, Provider, Tier, Usage

_GEO = nodes.GeoLocation(name="Tokyo", latitude=35.68, longitude=139.69, country="Japan")
_POIS = [nodes.POI(name="Senso-ji", category="temples", latitude=35.71, longitude=139.79)]
_WX = [
    nodes.WeatherDaily(date="2026-09-15", temp_max_c=26.0, temp_min_c=20.0, precipitation_mm=0.0)
]


class _FakeProvider:
    async def complete(self, messages: Any, model: str, tier: Tier, *, max_tokens: int = 1024):
        return LLMResponse(
            text="Day 1: Senso-ji.",
            provider=Provider.OPENAI,
            model=model,
            tier=tier,
            usage=Usage(input_tokens=100, output_tokens=50, cost_usd=0.0008),
        )


@pytest.fixture
def spans(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(trace, "_TRACER_PROVIDER", provider)
    return exporter


@pytest.fixture(autouse=True)
def _tools(monkeypatch):
    async def geocode(city):
        return _GEO

    async def find_pois(lat, lon, interest, **kw):
        return list(_POIS)

    async def forecast(lat, lon, *, days=3):
        return list(_WX)

    monkeypatch.setattr(nodes, "geocode", geocode)
    monkeypatch.setattr(nodes, "find_pois", find_pois)
    monkeypatch.setattr(nodes, "forecast", forecast)


def test_run_emits_nested_trace(spans):
    gateway = LLMGateway({Provider.OPENAI: _FakeProvider()})
    itin = asyncio.run(plan(PlanRequest(city="Tokyo", interests=["temples"]), gateway=gateway))
    assert itin.grounded is True

    finished = spans.get_finished_spans()
    names = {s.name for s in finished}
    assert "agent.plan" in names
    assert {"agent.geocode", "agent.gather", "agent.compose", "agent.critic"} <= names
    assert "llm.complete" in names  # produced by the real gateway path

    llm = next(s for s in finished if s.name == "llm.complete")
    assert llm.attributes is not None
    assert llm.attributes["llm.cost_usd"] == 0.0008

    run = next(s for s in finished if s.name == "agent.plan")
    assert run.attributes is not None
    assert run.attributes["run.id"] == "sync"
