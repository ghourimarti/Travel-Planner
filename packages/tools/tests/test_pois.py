"""tp_tools.pois — mocked Overpass (no network)."""

from __future__ import annotations

import asyncio

import respx
from httpx import Response
from tp_tools.pois import find_pois

_URL = "https://overpass-api.de/api/interpreter"
_WIKI = "https://en.wikipedia.org/w/api.php"


def test_parses_named_elements_and_skips_unnamed() -> None:
    with respx.mock:
        respx.get(_URL).mock(
            return_value=Response(
                200,
                json={
                    "elements": [
                        {
                            "type": "node",
                            "lat": 35.03,
                            "lon": 135.72,
                            "tags": {"name": "Kinkaku-ji", "amenity": "place_of_worship"},
                        },
                        # unnamed element -> skipped
                        {"type": "node", "lat": 35.0, "lon": 135.7, "tags": {}},
                    ]
                },
            )
        )
        pois = asyncio.run(find_pois(35.0, 135.7, "temples", endpoint=_URL))
    assert len(pois) == 1
    assert pois[0].name == "Kinkaku-ji"
    assert pois[0].category == "temples"


def test_default_uses_wikipedia_without_overpass(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # No endpoint and no OVERPASS_URL -> Overpass is skipped entirely.
    monkeypatch.delenv("OVERPASS_URL", raising=False)
    with respx.mock:
        respx.get(_WIKI).mock(
            return_value=Response(
                200,
                json={
                    "query": {
                        "geosearch": [{"title": "Fushimi Inari", "lat": 34.96, "lon": 135.77}]
                    }
                },
            )
        )
        pois = asyncio.run(find_pois(34.96, 135.77, "temples"))
    assert [p.name for p in pois] == ["Fushimi Inari"]


def test_falls_back_to_wikipedia_when_overpass_fails() -> None:
    with respx.mock:
        respx.get(_URL).mock(return_value=Response(406, text="blocked"))  # WAF block
        respx.get(_WIKI).mock(
            return_value=Response(
                200,
                json={
                    "query": {
                        "geosearch": [
                            {"title": "Tokyo National Museum", "lat": 35.71, "lon": 139.77},
                            {"title": "Senso-ji", "lat": 35.71, "lon": 139.79},
                        ]
                    }
                },
            )
        )
        pois = asyncio.run(find_pois(35.68, 139.69, "history", endpoint=_URL))
    assert [p.name for p in pois] == ["Tokyo National Museum", "Senso-ji"]
    # Wikipedia GeoSearch can't verify interest, so results are labeled honestly as
    # "sights" (not the searched interest — that was the old "everything is food" lie).
    assert pois[0].category == "sights"


def test_falls_back_to_wikipedia_when_overpass_empty() -> None:
    with respx.mock:
        respx.get(_URL).mock(return_value=Response(200, json={"elements": []}))  # reachable, empty
        respx.get(_WIKI).mock(
            return_value=Response(
                200,
                json={
                    "query": {"geosearch": [{"title": "Ueno Park", "lat": 35.71, "lon": 139.77}]}
                },
            )
        )
        pois = asyncio.run(find_pois(35.68, 139.69, "nature", endpoint=_URL))
    assert [p.name for p in pois] == ["Ueno Park"]


def test_category_comes_from_osm_tags_not_search_interest() -> None:
    # A place's OWN tags decide its category, not the interest we searched under. Here we
    # search "history" but the element is a restaurant -> it should read as "food".
    with respx.mock:
        respx.get(_URL).mock(
            return_value=Response(
                200,
                json={
                    "elements": [
                        {
                            "type": "node",
                            "lat": 35.0,
                            "lon": 135.0,
                            "tags": {"name": "Ichiran Ramen", "amenity": "restaurant"},
                        },
                        {
                            "type": "node",
                            "lat": 35.1,
                            "lon": 135.1,
                            "tags": {"name": "City Museum", "tourism": "museum"},
                        },
                    ]
                },
            )
        )
        pois = asyncio.run(find_pois(35.0, 135.0, "history", endpoint=_URL))
    by_name = {p.name: p.category for p in pois}
    assert by_name["Ichiran Ramen"] == "food"
    assert by_name["City Museum"] == "museums"


def test_handles_way_center_coords() -> None:
    with respx.mock:
        respx.get(_URL).mock(
            return_value=Response(
                200,
                json={
                    "elements": [
                        {
                            "type": "way",
                            "center": {"lat": 35.1, "lon": 135.8},
                            "tags": {"name": "Nijo Castle", "tourism": "attraction"},
                        }
                    ]
                },
            )
        )
        pois = asyncio.run(find_pois(35.0, 135.7, "history", endpoint=_URL))
    assert pois[0].name == "Nijo Castle"
    assert pois[0].latitude == 35.1
