"""S9c: the planner streams a progress event per completed graph node (offline)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
import tp_agents.nodes as nodes
from tp_agents import PlanRequest, TripRequest, plan, plan_trip
from tp_core.llm import LLMResponse, Provider, Tier, Usage
from tp_tools.models import POI, GeoLocation, WeatherDaily

_GEO = GeoLocation(name="Tokyo", latitude=35.68, longitude=139.69, country="Japan")
_POIS = [POI(name="Senso-ji", category="temples", latitude=35.71, longitude=139.79)]
_WX = [WeatherDaily(date="2026-09-15", temp_max_c=26.0, temp_min_c=20.0, precipitation_mm=0.0)]
_NODES = {"geocode", "gather", "compose", "critic"}


class _FakeGateway:
    async def complete(self, messages: Any, tier: Tier, *, max_tokens: int = 1024) -> LLMResponse:
        return LLMResponse(
            text="Day 1: Senso-ji.",
            provider=Provider.OPENAI,
            model="gpt-4o",
            tier=tier,
            usage=Usage(input_tokens=100, output_tokens=50, cost_usd=0.0008),
        )


@pytest.fixture(autouse=True)
def _sqlite(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'cp.db').as_posix()}")

    async def geocode(city):
        return _GEO

    async def find_pois(lat, lon, interest, **kw):
        return list(_POIS)

    async def forecast(lat, lon, *, days=3):
        return list(_WX)

    monkeypatch.setattr(nodes, "geocode", geocode)
    monkeypatch.setattr(nodes, "find_pois", find_pois)
    monkeypatch.setattr(nodes, "forecast", forecast)


def test_plan_streams_a_node_event_per_node():
    events: list[tuple[str, str | None]] = []

    async def on_event(node, delta, *, city=None):
        events.append((node, city))

    itin = asyncio.run(
        plan(
            PlanRequest(city="Tokyo", interests=["temples"]),
            gateway=_FakeGateway(),
            run_id="r1",
            on_event=on_event,
        )
    )
    assert events[0][0] == "geocode"
    assert {n for n, _ in events} == _NODES
    assert all(c is None for _, c in events)
    assert itin.grounded is True


def test_trip_tags_events_with_city():
    events: list[tuple[str, str | None]] = []

    async def on_event(node, delta, *, city=None):
        events.append((node, city))

    asyncio.run(
        plan_trip(
            TripRequest(cities=["Tokyo"], interests=["temples"], days=1),
            gateway=_FakeGateway(),
            run_id="t1",
            on_event=on_event,
        )
    )
    assert events
    assert all(c == "Tokyo" for _, c in events)
    assert {n for n, _ in events} == _NODES
