"""POI tool: interest mapping (unit) + parsing (mocked) + live integration."""

from __future__ import annotations

from typing import Any

import pytest

import tp_tools.pois as pois_mod
from tp_tools.pois import _build_query, search_pois


def test_unknown_interest_falls_back_to_attraction() -> None:
    query = _build_query(48.85, 2.35, ["zzz-unknown"], 4000, 30)
    assert 'tourism"="attraction' in query


def test_known_interest_maps_to_tags() -> None:
    query = _build_query(48.85, 2.35, ["art"], 4000, 30)
    assert 'tourism"="museum' in query
    assert 'tourism"="gallery' in query


async def test_search_pois_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake(*_a: Any, **_k: Any) -> dict[str, Any]:
        return {
            "elements": [
                {
                    "type": "node",
                    "lat": 48.86,
                    "lon": 2.34,
                    "tags": {"name": "Louvre", "tourism": "museum"},
                },
                {
                    "type": "way",
                    "center": {"lat": 48.86, "lon": 2.33},
                    "tags": {"name": "Orsay", "tourism": "museum"},
                },
                {"type": "node", "lat": 1.0, "lon": 1.0, "tags": {}},  # unnamed -> skipped
            ]
        }

    monkeypatch.setattr(pois_mod, "fetch_json", _fake)
    pois = await search_pois(48.85, 2.35, ["art"])
    assert [p.name for p in pois] == ["Louvre", "Orsay"]
    assert pois[0].category == "tourism:museum"
    assert pois[1].latitude == 48.86  # taken from way center


@pytest.mark.integration
async def test_search_pois_live() -> None:
    pois = await search_pois(48.8566, 2.3522, ["art", "food"], radius_m=3000, limit=20)
    assert len(pois) > 0
    assert all(p.name for p in pois)
