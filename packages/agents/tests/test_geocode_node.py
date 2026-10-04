"""geocode_node surfaces WHERE a plan was anchored when the match is obscure.

Grounding protects against fabrication, not against a wrong anchor: `kyota` resolves to a
real village in Uganda, and used to become a confident, zero-warning itinerary there.
"""

from __future__ import annotations

import asyncio
from typing import Any

from tp_agents import nodes
from tp_agents.schemas import PlanRequest
from tp_tools.models import GeoLocation


def _run(monkeypatch: Any, geo: GeoLocation | None, city: str = "kyota") -> dict[str, Any]:
    async def direct(key: str, ttl: int, factory: Any, adapter: Any, **kwargs: Any) -> Any:
        return await factory()

    async def fake_geocode(_: str) -> GeoLocation | None:
        return geo

    monkeypatch.setattr(nodes, "cache_aside", direct)
    monkeypatch.setattr(nodes, "geocode", fake_geocode)
    state: Any = {"request": PlanRequest(city=city, interests=["temples"]), "warnings": []}
    return asyncio.run(nodes.geocode_node(state))


def test_obscure_anchor_is_named_in_a_visible_warning(monkeypatch: Any) -> None:
    geo = GeoLocation(name="kyota", latitude=0.613, longitude=31.454, country="Uganda",
                      display_name="Kyota, Kiboga, Central Region, Uganda",
                      importance=0.147, kind="village")
    out = _run(monkeypatch, geo)
    assert out["geo"] is geo  # still planned - Hallstatt scores the same, refusing is wrong
    warning = next(w for w in out["warnings"] if w.startswith("Planned for Kyota, Uganda"))
    assert "add the country" in warning
    # Neutral on purpose: the score cannot tell a typo from a famous small village.
    assert "little-known" not in warning


def test_prominent_anchor_adds_no_warning(monkeypatch: Any) -> None:
    geo = GeoLocation(name="Kyoto", latitude=35.01, longitude=135.77, country="Japan",
                      importance=0.709, kind="city")
    out = _run(monkeypatch, geo, city="Kyoto")
    assert "warnings" not in out


def test_unknown_prominence_is_not_treated_as_obscure(monkeypatch: Any) -> None:
    """A cached lookup from before `importance` existed must not start warning."""
    geo = GeoLocation(name="Kyoto", latitude=35.01, longitude=135.77)
    out = _run(monkeypatch, geo, city="Kyoto")
    assert "warnings" not in out
