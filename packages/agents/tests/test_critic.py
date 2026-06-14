"""S7: the critic catches an invented place and drives a CAPPED corrective loop.

A scripted gateway returns compose/critic responses in order; tools are mocked.
No network, no real LLM.
"""

from __future__ import annotations

import asyncio

import pytest
import tp_agents.nodes as nodes
from tp_agents import PlanRequest, plan
from tp_core.llm import LLMResponse, Message, Provider, Tier, Usage
from tp_tools.models import POI, GeoLocation, WeatherDaily

_GEO = GeoLocation(name="Tokyo", latitude=35.0, longitude=139.0)
_POIS = [POI(name="Senso-ji", category="temples", latitude=0.0, longitude=0.0)]


def _patch_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_geocode(city: str) -> GeoLocation:
        return _GEO

    async def fake_find_pois(lat: float, lon: float, interest: str, **kw: object) -> list[POI]:
        return list(_POIS)

    async def fake_forecast(lat: float, lon: float, *, days: int = 3) -> list[WeatherDaily]:
        return []

    monkeypatch.setattr(nodes, "geocode", fake_geocode)
    monkeypatch.setattr(nodes, "find_pois", fake_find_pois)
    monkeypatch.setattr(nodes, "forecast", fake_forecast)


class _ScriptedGateway:
    """Returns canned responses in order (clamps to the last once exhausted)."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.calls = 0

    async def complete(
        self, messages: list[Message], tier: Tier, *, max_tokens: int = 1024
    ) -> LLMResponse:
        text = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return LLMResponse(
            text=text,
            provider=Provider.OPENAI,
            model="gpt-4o",
            tier=tier,
            usage=Usage(input_tokens=10, output_tokens=5, cost_usd=0.001),
        )


def test_critic_catches_invention_and_revises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_tools(monkeypatch)
    gw = _ScriptedGateway(
        [
            "Day 1: visit Senso-ji and FakePlace.",  # compose #1 (invents FakePlace)
            '{"ok": false, "invented_places": ["FakePlace"], "issues": []}',  # critic #1
            "Day 1: visit Senso-ji.",  # compose #2 (corrected)
            '{"ok": true, "invented_places": [], "issues": []}',  # critic #2
        ]
    )
    itin = asyncio.run(plan(PlanRequest(city="Tokyo", interests=["temples"]), gateway=gw))
    assert itin.corrections == 1
    assert "FakePlace" not in itin.summary_markdown
    assert gw.calls == 4  # compose, critic, compose, critic


def test_corrective_loop_respects_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_tools(monkeypatch)
    flag = '{"ok": false, "invented_places": ["X"], "issues": []}'
    gw = _ScriptedGateway(["Day 1: X.", flag, "Day 1: X.", flag])  # critic always complains
    itin = asyncio.run(plan(PlanRequest(city="Tokyo", interests=["temples"]), gateway=gw))
    assert itin.corrections == 1  # exactly one re-compose, then stop at the cap
    assert gw.calls == 4  # no infinite loop despite the critic still flagging
