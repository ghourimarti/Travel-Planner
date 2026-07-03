"""S4 slice: the planner graph grounds in the provided POIs and degrades honestly.

Tools and the gateway are mocked at the seam — no network, no OpenAI spend.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
import tp_agents.nodes as nodes
from tp_agents import PlanRequest, plan
from tp_core.llm import LLMResponse, Message, Provider, Tier, Usage
from tp_tools.models import POI, GeoLocation, WeatherDaily


class _FakeGateway:
    """Records calls; returns a canned grounded response."""

    def __init__(self, text: str = "Day 1: visit Senso-ji.") -> None:
        self.text = text
        self.calls = 0

    async def complete(
        self, messages: list[Message], tier: Tier, *, max_tokens: int = 1024
    ) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            text=self.text,
            provider=Provider.OPENAI,
            model="gpt-4o",
            tier=tier,
            usage=Usage(input_tokens=100, output_tokens=50, cost_usd=0.0008),
        )


_GEO = GeoLocation(name="Tokyo", latitude=35.68, longitude=139.69, country="Japan")
_POIS = [POI(name="Senso-ji", category="temples", latitude=35.71, longitude=139.79)]
_WX = [WeatherDaily(date="2026-09-15", temp_max_c=26.0, temp_min_c=20.0, precipitation_mm=0.0)]


def _patch_tools(
    monkeypatch: pytest.MonkeyPatch,
    *,
    geo: GeoLocation | None = _GEO,
    pois: list[POI] | None = None,
) -> None:
    resolved_pois = _POIS if pois is None else pois

    async def fake_geocode(city: str) -> GeoLocation | None:
        return geo

    async def fake_find_pois(lat: float, lon: float, interest: str, **kw: Any) -> list[POI]:
        return list(resolved_pois)

    async def fake_forecast(lat: float, lon: float, *, days: int = 3) -> list[WeatherDaily]:
        return list(_WX)

    monkeypatch.setattr(nodes, "geocode", fake_geocode)
    monkeypatch.setattr(nodes, "find_pois", fake_find_pois)
    monkeypatch.setattr(nodes, "forecast", fake_forecast)


def test_plan_is_grounded_in_provided_pois(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_tools(monkeypatch)
    gw = _FakeGateway()
    itin = asyncio.run(plan(PlanRequest(city="Tokyo", interests=["temples"]), gateway=gw))
    assert gw.calls == 2  # compose + critic
    assert itin.grounded is True
    assert [p.name for p in itin.pois_used] == ["Senso-ji"]
    assert itin.cost_usd == pytest.approx(0.0008)
    assert "Senso-ji" in itin.summary_markdown


def test_grounded_itinerary_populates_structured_days(monkeypatch: pytest.MonkeyPatch) -> None:
    pois = [
        POI(name="Senso-ji", category="temples", latitude=35.71, longitude=139.79),
        POI(name="Meiji Shrine", category="temples", latitude=35.67, longitude=139.70),
        POI(name="Ueno Park", category="parks", latitude=35.71, longitude=139.77),
    ]
    _patch_tools(monkeypatch, pois=pois)
    itin = asyncio.run(
        plan(PlanRequest(city="Tokyo", interests=["temples"], days=2), gateway=_FakeGateway())
    )
    # The structured days are filled (not just the markdown) — balanced, front-loaded.
    assert [d.day for d in itin.days] == [1, 2]
    assert [len(d.items) for d in itin.days] == [2, 1]
    placed = [i.name for d in itin.days for i in d.items]
    assert placed == ["Senso-ji", "Meiji Shrine", "Ueno Park"]  # all real POIs, in order
    # Every map pin traces back to a grounded POI — nothing invented.
    assert {i.name for d in itin.days for i in d.items} <= {p.name for p in itin.pois_used}


def test_days_are_capped_at_a_realistic_stop_count(monkeypatch: pytest.MonkeyPatch) -> None:
    # 12 grounded POIs but only 1 requested day must NOT dump all 12 into that day — a real
    # day is a handful of stops (regression: multi-city trips collapsing to ~1 day/city).
    pois = [
        POI(name=f"Place {i}", category="sights", latitude=35.7 + i / 100, longitude=139.7)
        for i in range(12)
    ]
    _patch_tools(monkeypatch, pois=pois)
    itin = asyncio.run(
        plan(PlanRequest(city="Tokyo", interests=["sights"], days=1), gateway=_FakeGateway())
    )
    assert len(itin.days) == 1
    assert len(itin.days[0].items) <= nodes._MAX_POIS_PER_DAY  # not all 12 crammed in
    # The plan and the map agree — pois_used matches what's actually scheduled.
    assert len(itin.pois_used) == len(itin.days[0].items)


def test_unknown_city_degrades_without_calling_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_tools(monkeypatch, geo=None)
    gw = _FakeGateway()
    itin = asyncio.run(plan(PlanRequest(city="Nowhereville", interests=["food"]), gateway=gw))
    assert gw.calls == 0  # no LLM spend on an unresolvable city
    assert itin.grounded is False
    assert any("Nowhereville" in w for w in itin.warnings)


def test_empty_pois_still_composes_but_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_tools(monkeypatch, pois=[])
    gw = _FakeGateway()
    itin = asyncio.run(plan(PlanRequest(city="Tokyo", interests=["food"]), gateway=gw))
    assert gw.calls == 1
    assert itin.grounded is False
    assert itin.days == []  # nothing to ground -> no fabricated days
    assert any("No POIs" in w for w in itin.warnings)


class _FakeRetriever:
    def __init__(self, pois: list[POI]) -> None:
        self._pois = pois

    async def retrieve(
        self, city: str, interests: list[str], *, tenant_id: str | None = None
    ) -> list[POI]:
        return list(self._pois)


def test_plan_uses_retriever_as_primary_poi_source(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_tools(monkeypatch)
    live_called = {"hit": False}

    async def tracking_find_pois(lat: float, lon: float, interest: str, **kw: Any) -> list[POI]:
        live_called["hit"] = True
        return []

    monkeypatch.setattr(nodes, "find_pois", tracking_find_pois)
    gw = _FakeGateway()
    retriever = _FakeRetriever(
        [POI(name="Corpus Place", category="temples", latitude=0.0, longitude=0.0)]
    )
    itin = asyncio.run(
        plan(PlanRequest(city="Tokyo", interests=["temples"]), gateway=gw, retriever=retriever)
    )
    assert [p.name for p in itin.pois_used] == ["Corpus Place"]
    assert live_called["hit"] is False  # corpus retrieval pre-empts the live tool
