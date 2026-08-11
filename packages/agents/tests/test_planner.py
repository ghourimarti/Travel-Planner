"""The planner graph grounds in the provided POIs and degrades honestly.

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
    # Cost covers EVERY call the run made — the compose and the frontier-tier critic
    # (0.0008 each here), not just the compose. The budget guard reads this number,
    # so under-counting it would let a run overshoot its cap by the critic's share.
    assert itin.cost_usd == pytest.approx(0.0016)
    assert "Senso-ji" in itin.summary_markdown


def test_prose_cannot_name_an_ungrounded_venue(monkeypatch: pytest.MonkeyPatch) -> None:
    # #4 structural grounding: the LLM prose names a real Kyoto temple that is NOT among the
    # retrieved POIs — it must be dropped, and the summary must name only grounded places.
    _patch_tools(monkeypatch)  # only allowed POI = Senso-ji
    gw = _FakeGateway(text="Begin at the famous Ryoan-ji rock garden before exploring.")
    itin = asyncio.run(plan(PlanRequest(city="Tokyo", interests=["temples"]), gateway=gw))
    assert "Ryoan-ji" not in itin.summary_markdown  # ungrounded venue stripped from prose
    assert "Senso-ji" in itin.summary_markdown  # grounded skeleton preserved


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


def test_multi_day_single_city_honors_requested_days(monkeypatch: pytest.MonkeyPatch) -> None:
    # #8: a longer request now produces more grounded days (bounded only by available POIs),
    # not the old hard cap of 3.
    pois = [
        POI(name=f"Spot {i}", category="sights", latitude=35.0 + i / 100, longitude=139.0)
        for i in range(8)
    ]
    _patch_tools(monkeypatch, pois=pois)
    itin = asyncio.run(
        plan(PlanRequest(city="Tokyo", interests=["sights"], days=4), gateway=_FakeGateway())
    )
    assert [d.day for d in itin.days] == [1, 2, 3, 4]  # 4 days honored (was capped at 3)


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


def test_merge_interest_buckets_dedups_and_interleaves() -> None:
    # The Wikipedia fallback returns the SAME nearby places for every interest. Naive
    # concatenation repeats each place N times and, after truncation, keeps only the first
    # interest ("every POI is food"). _merge_interest_buckets must dedup + interleave.
    food = [
        POI(name="Ramen Bar", category="food", latitude=35.0, longitude=139.0),
        POI(name="Shared Landmark", category="food", latitude=35.5, longitude=139.5),
    ]
    temples = [
        POI(name="Old Shrine", category="temples", latitude=35.1, longitude=139.1),
        POI(name="Shared Landmark", category="temples", latitude=35.5, longitude=139.5),  # dup
    ]
    merged = nodes._merge_interest_buckets([food, temples])
    names = [p.name for p in merged]
    assert names.count("Shared Landmark") == 1  # deduped across interests
    # Interleaved: first of each interest before the second of either.
    assert names[:2] == ["Ramen Bar", "Old Shrine"]
    assert set(names) == {"Ramen Bar", "Old Shrine", "Shared Landmark"}


def test_live_pois_across_interests_are_deduped_in_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    # End-to-end: two interests whose live lookups return an overlapping place must not
    # produce duplicate stops in the itinerary (regression for the repeated-POI bug).
    shared = POI(name="Central Park", category="sights", latitude=40.78, longitude=-73.96)
    unique = POI(name="The Met", category="museums", latitude=40.77, longitude=-73.96)

    async def fake_geocode(city: str):  # type: ignore[no-untyped-def]
        return GeoLocation(name="New York", latitude=40.71, longitude=-74.0, country="USA")

    async def fake_find_pois(lat: float, lon: float, interest: str, **kw: Any) -> list[POI]:
        return [shared, unique]  # same places returned for every interest

    async def fake_forecast(lat: float, lon: float, *, days: int = 3) -> list[WeatherDaily]:
        return list(_WX)

    monkeypatch.setattr(nodes, "geocode", fake_geocode)
    monkeypatch.setattr(nodes, "find_pois", fake_find_pois)
    monkeypatch.setattr(nodes, "forecast", fake_forecast)

    itin = asyncio.run(
        plan(
            PlanRequest(city="New York", interests=["nature", "museums"], days=1),
            gateway=_FakeGateway(),
        )
    )
    names = [p.name for p in itin.pois_used]
    assert sorted(names) == ["Central Park", "The Met"]  # deduped, not 4 entries


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
