"""S11a/S11b: a planner run emits a nested OTel trace (run -> nodes -> llm), hermetically.

The gateway wraps a fake PROVIDER (not a fake gateway), so the real gateway code path —
and its ``llm.complete`` span with GenAI/cost attributes — is exercised without a network
call or key. S11b adds the Langfuse export wiring (asserted without any Langfuse network).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
import tp_agents.coordinator as coordinator
import tp_agents.nodes as nodes
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from tp_agents import PlanRequest, TripRequest, plan, plan_trip
from tp_core import tracing
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
    # GenAI semantic conventions so Langfuse renders this as a generation (S11b).
    assert llm.attributes["gen_ai.request.model"]
    assert llm.attributes["gen_ai.usage.input_tokens"] == 100
    assert llm.attributes["gen_ai.usage.cost"] == 0.0008

    critic = next(s for s in finished if s.name == "agent.critic")
    assert critic.attributes is not None
    assert "critic.ok" in critic.attributes  # verdict surfaced on the span (S11b)
    assert "critic.has_issues" in critic.attributes

    run = next(s for s in finished if s.name == "agent.plan")
    assert run.attributes is not None
    assert run.attributes["run.id"] == "sync"


def test_multi_city_trip_span(spans, monkeypatch):
    async def no_legs(points):  # keep routing off the network in tests
        return []

    monkeypatch.setattr(coordinator, "route", no_legs)
    gateway = LLMGateway({Provider.OPENAI: _FakeProvider()})
    req = TripRequest(cities=["Tokyo", "Kyoto"], interests=["temples"], days=2)
    trip = asyncio.run(plan_trip(req, gateway=gateway))
    assert len(trip.cities) == 2

    finished = spans.get_finished_spans()
    root = next(s for s in finished if s.name == "trip.plan")
    assert root.attributes is not None
    assert root.attributes["trip.cities_requested"] == 2
    assert root.attributes["trip.cities_succeeded"] == 2
    assert root.attributes["trip.cities_failed"] == 0
    assert root.attributes["trip.partial"] is False


def test_langfuse_exporter_added_when_keys_set(monkeypatch):
    class _Cfg:
        langfuse_public_key = "pk"
        langfuse_secret_key = "sk"
        langfuse_host = "https://lf.example.com/"

    monkeypatch.setattr("tp_core.settings.get_settings", lambda: _Cfg())

    captured: dict[str, Any] = {}

    class _FakeExporter:
        def __init__(self, *, endpoint, headers):
            captured["endpoint"] = endpoint
            captured["headers"] = headers

    monkeypatch.setattr(
        "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
        _FakeExporter,
    )
    provider = TracerProvider()
    added: list[Any] = []
    monkeypatch.setattr(provider, "add_span_processor", added.append)

    tracing._add_langfuse_exporter(provider)

    assert len(added) == 1
    assert captured["endpoint"] == "https://lf.example.com/api/public/otel/v1/traces"
    assert captured["headers"]["Authorization"].startswith("Basic ")


def test_langfuse_exporter_skipped_without_keys(monkeypatch):
    class _Cfg:
        langfuse_public_key = None
        langfuse_secret_key = None
        langfuse_host = "https://cloud.langfuse.com"

    monkeypatch.setattr("tp_core.settings.get_settings", lambda: _Cfg())
    provider = TracerProvider()
    added: list[Any] = []
    monkeypatch.setattr(provider, "add_span_processor", added.append)

    tracing._add_langfuse_exporter(provider)

    assert added == []
