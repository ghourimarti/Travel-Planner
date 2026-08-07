"""The multi-city coordinator fans out, merges, and degrades to partial results.

The per-city worker graph and the routing tool are mocked, so this isolates the
coordinator logic — no network, no LLM.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
import tp_agents.coordinator as coordinator
from tp_agents import TripRequest, plan_trip
from tp_agents.schemas import Itinerary
from tp_tools.models import GeoLocation, RouteLeg


def _itin(
    city: str, lat: float, lon: float, *, grounded: bool = True, cost: float = 0.01
) -> Itinerary:
    return Itinerary(
        city=city,
        summary_markdown=f"{city} plan",
        grounded=grounded,
        cost_usd=cost,
        center=GeoLocation(name=city, latitude=lat, longitude=lon),
    )


class _FakeGraph:
    def __init__(self, by_city: dict[str, Itinerary | Exception]) -> None:
        self._by = by_city

    async def ainvoke(self, state: dict[str, Any], *a: Any, **k: Any) -> dict[str, Any]:
        city = state["request"].city
        res = self._by[city]
        if isinstance(res, Exception):
            raise res
        return {"itinerary": res}


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    by_city: dict[str, Itinerary | Exception],
    legs: list[RouteLeg] | None = None,
) -> None:
    monkeypatch.setattr(
        coordinator, "build_planner_graph", lambda gw, retr=None, **kw: _FakeGraph(by_city)
    )

    async def fake_route(points: list[tuple[str, float, float]]) -> list[RouteLeg]:
        return legs or []

    monkeypatch.setattr(coordinator, "route", fake_route)


def test_fans_out_and_merges(monkeypatch: pytest.MonkeyPatch) -> None:
    by: dict[str, Itinerary | Exception] = {
        "Tokyo": _itin("Tokyo", 35.6, 139.7),
        "Kyoto": _itin("Kyoto", 35.0, 135.7),
    }
    legs = [RouteLeg(from_name="Tokyo", to_name="Kyoto", distance_m=450_000, duration_s=18_000)]
    _patch(monkeypatch, by, legs)
    req = TripRequest(cities=["Tokyo", "Kyoto"], interests=["temples"], days=4)
    trip = asyncio.run(plan_trip(req, gateway=object()))  # type: ignore[arg-type]
    assert [c.city for c in trip.cities] == ["Tokyo", "Kyoto"]
    assert len(trip.inter_city_legs) == 1
    assert "Tokyo" in trip.summary_markdown and "Kyoto" in trip.summary_markdown
    assert trip.cost_usd == pytest.approx(0.02)
    assert trip.failed_cities == []


def test_partial_results_when_one_city_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    by: dict[str, Itinerary | Exception] = {
        "Tokyo": _itin("Tokyo", 35.6, 139.7),
        "Atlantis": RuntimeError("boom"),
    }
    _patch(monkeypatch, by, [])
    req = TripRequest(cities=["Tokyo", "Atlantis"], interests=["food"], days=2)
    trip = asyncio.run(plan_trip(req, gateway=object()))  # type: ignore[arg-type]
    assert [c.city for c in trip.cities] == ["Tokyo"]  # the good city still ships
    assert trip.failed_cities == ["Atlantis"]
    assert any("Atlantis" in w for w in trip.warnings)
