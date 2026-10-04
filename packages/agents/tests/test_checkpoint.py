"""The LangGraph checkpointer resumes a crashed run from the last completed node.

Deterministic + offline: tools are monkeypatched with call-counters and the gateway is
canned, so 'crash then resume' is exercised without Docker, keys, or a real worker death.
The checkpoint DB is a throwaway file-SQLite (a FILE, since :memory: is per-connection).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
import tp_agents.graph as graph_mod
import tp_agents.nodes as nodes
from tp_agents import plan_trip
from tp_agents.checkpoint import make_checkpointer
from tp_agents.graph import build_planner_graph, run_graph
from tp_agents.schemas import PlanRequest, TripRequest
from tp_agents.state import PlannerState
from tp_core.llm import LLMResponse, Provider, Tier, Usage
from tp_tools.models import POI, GeoLocation, WeatherDaily

_GEO = GeoLocation(name="Tokyo", latitude=35.68, longitude=139.69, country="Japan")
_POIS = [POI(name="Senso-ji", category="temples", latitude=35.71, longitude=139.79)]
_WX = [WeatherDaily(date="2026-09-15", temp_max_c=26.0, temp_min_c=20.0, precipitation_mm=0.0)]


class _FakeGateway:
    async def complete(self, messages: Any, tier: Tier, *, max_tokens: int = 1024) -> LLMResponse:
        return LLMResponse(
            text="Day 1: visit Senso-ji.",
            provider=Provider.OPENAI,
            model="gpt-4o",
            tier=tier,
            usage=Usage(input_tokens=100, output_tokens=50, cost_usd=0.0008),
        )


@pytest.fixture
def counted_tools(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'cp.db').as_posix()}")
    counts = {"geocode": 0, "pois": 0}

    async def geocode(city):
        counts["geocode"] += 1
        return _GEO

    async def find_pois(lat, lon, interest, **kw):
        counts["pois"] += 1
        return list(_POIS)

    async def forecast(lat, lon, *, days=3):
        return list(_WX)

    monkeypatch.setattr(nodes, "geocode", geocode)
    monkeypatch.setattr(nodes, "find_pois", find_pois)
    monkeypatch.setattr(nodes, "forecast", forecast)
    return counts


def _run_once(gw, thread):
    initial: PlannerState = {
        "request": PlanRequest(city="Tokyo", interests=["temples"]),
        "warnings": [],
        "max_compose_attempts": 2,
    }

    async def go():
        async with make_checkpointer(thread) as cp:
            graph = build_planner_graph(gw, None, checkpointer=cp)
            return await run_graph(graph, cp, thread, initial)

    return asyncio.run(go())


def test_resume_skips_completed_nodes(counted_tools, monkeypatch):
    real_compose = graph_mod.compose_node
    state = {"n": 0}

    async def flaky_compose(s, gateway):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("worker died mid-compose")
        return await real_compose(s, gateway)

    monkeypatch.setattr(graph_mod, "compose_node", flaky_compose)
    gw = _FakeGateway()

    with pytest.raises(RuntimeError):
        _run_once(gw, "run-xyz")
    assert counted_tools == {"geocode": 1, "pois": 1}  # geocode + gather ran once

    final = _run_once(gw, "run-xyz")  # redelivery -> resume from checkpoint
    assert counted_tools == {"geocode": 1, "pois": 1}  # NOT re-run -> resumed
    assert final["itinerary"].grounded is True
    assert final["itinerary"].pois_used[0].name == "Senso-ji"


def test_completed_run_resumes_from_end(counted_tools):
    gw = _FakeGateway()
    first = _run_once(gw, "run-done")
    assert counted_tools == {"geocode": 1, "pois": 1}
    assert first["itinerary"].grounded is True

    second = _run_once(gw, "run-done")  # already at END -> nothing re-executes
    assert counted_tools == {"geocode": 1, "pois": 1}
    assert second["itinerary"].grounded is True


def test_trip_finished_city_resumes_free(counted_tools):
    gw = _FakeGateway()
    req = TripRequest(cities=["Tokyo"], interests=["temples"], days=1)
    asyncio.run(plan_trip(req, gateway=gw, retriever=None, run_id="trip-1"))
    assert counted_tools == {"geocode": 1, "pois": 1}

    trip = asyncio.run(plan_trip(req, gateway=gw, retriever=None, run_id="trip-1"))
    assert counted_tools == {"geocode": 1, "pois": 1}  # city resumed from END
    assert trip.cities[0].grounded is True


def test_state_types_round_trip_without_the_unregistered_type_warning(caplog):
    """Every project type in graph state must survive the serializer EXPLICITLY allowed.

    Passing an allowlist makes LangGraph strict: anything not listed is BLOCKED on
    resume. So this round-trips a state holding every model that can appear in it, and
    fails if any comes back altered or triggers the unregistered-type warning.
    """
    import logging

    from tp_agents.checkpoint import state_serde
    from tp_agents.schemas import (
        CriticVerdict,
        DayPlan,
        Itinerary,
        ItineraryItem,
        PlanRequest,
        TripItinerary,
        TripRequest,
    )
    from tp_tools.models import POI, GeoLocation, RouteLeg, WeatherDaily

    item = ItineraryItem(name="Kinkaku-ji", category="temples", latitude=35.0, longitude=135.7)
    itinerary = Itinerary(city="Kyoto", summary_markdown="x", days=[DayPlan(day=1, items=[item])])
    state = {
        "request": PlanRequest(city="Kyoto", interests=["temples"]),
        "geo": GeoLocation(name="Kyoto", latitude=35.0, longitude=135.7, importance=0.7),
        "pois": [POI(name="Kinkaku-ji", category="temples", latitude=35.0, longitude=135.7)],
        "weather": [WeatherDaily(date="2026-09-29")],
        "route": [RouteLeg(from_name="a", to_name="b", distance_m=1.0, duration_s=1.0)],
        "itinerary": itinerary,
        "critic_verdict": CriticVerdict(ok=True, issues=["none"]),
        "trip_request": TripRequest(cities=["Kyoto"], interests=["temples"]),
        "trip": TripItinerary(summary_markdown="x", cities=[itinerary]),
    }
    serde = state_serde()
    with caplog.at_level(logging.WARNING):
        restored = serde.loads_typed(serde.dumps_typed(state))
    assert restored == state
    assert "unregistered type" not in caplog.text
    assert "blocked" not in caplog.text.lower()
