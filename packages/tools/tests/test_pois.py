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


def _wiki_pages(*entries: tuple[str, float, float, list[str]]) -> dict[str, object]:
    """Build a ``generator=geosearch`` response payload from (title, lat, lon, categories)."""
    pages = {
        str(i): {
            "title": title,
            "coordinates": [{"lat": lat, "lon": lon}],
            "categories": [{"title": f"Category:{c}"} for c in categories],
        }
        for i, (title, lat, lon, categories) in enumerate(entries)
    }
    return {"query": {"pages": pages}}


def test_default_uses_wikipedia_without_overpass(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # No endpoint and no OVERPASS_URL -> Overpass is skipped entirely.
    monkeypatch.delenv("OVERPASS_URL", raising=False)
    with respx.mock:
        respx.get(_WIKI).mock(
            return_value=Response(
                200,
                json=_wiki_pages(
                    ("Fushimi Inari", 34.96, 135.77, ["Shinto shrines in Kyoto"]),
                ),
            )
        )
        pois = asyncio.run(find_pois(34.96, 135.77, "temples"))
    assert [p.name for p in pois] == ["Fushimi Inari"]
    assert pois[0].category == "temples"  # classified via its real Wikipedia category


def test_falls_back_to_wikipedia_when_overpass_fails() -> None:
    with respx.mock:
        respx.get(_URL).mock(return_value=Response(406, text="blocked"))  # WAF block
        respx.get(_WIKI).mock(
            return_value=Response(
                200,
                json=_wiki_pages(
                    (
                        "Tokyo National Museum",
                        35.71,
                        139.77,
                        ["Museums in Tokyo", "History museums"],
                    ),
                    ("Senso-ji", 35.71, 139.79, ["Buddhist temples in Tokyo"]),
                ),
            )
        )
        pois = asyncio.run(find_pois(35.68, 139.69, "history", endpoint=_URL))
    assert [p.name for p in pois] == ["Tokyo National Museum", "Senso-ji"]
    assert pois[0].category == "history"
    # Senso-ji doesn't match "history" keywords -> honestly labeled, not mislabeled.
    assert pois[1].category == "sights"


def test_falls_back_to_wikipedia_when_overpass_empty() -> None:
    with respx.mock:
        respx.get(_URL).mock(return_value=Response(200, json={"elements": []}))  # reachable, empty
        respx.get(_WIKI).mock(
            return_value=Response(
                200,
                json=_wiki_pages(("Ueno Park", 35.71, 139.77, ["Parks in Tokyo"])),
            )
        )
        pois = asyncio.run(find_pois(35.68, 139.69, "nature", endpoint=_URL))
    assert [p.name for p in pois] == ["Ueno Park"]
    assert pois[0].category == "nature"


def test_wikipedia_fallback_does_not_mislabel_unrelated_places() -> None:
    """Regression: every interest used to relabel the SAME nearby places, so a
    'beaches' search for Tokyo would tag a train station as a beach. Now a
    non-matching place is tagged the honest generic category instead."""
    with respx.mock:
        respx.get(_URL).mock(return_value=Response(200, json={"elements": []}))
        respx.get(_WIKI).mock(
            return_value=Response(
                200,
                json=_wiki_pages(
                    ("Yurakucho Station", 35.67, 139.76, ["Railway stations in Tokyo"]),
                ),
            )
        )
        pois = asyncio.run(find_pois(35.68, 139.69, "beaches", endpoint=_URL))
    assert pois[0].name == "Yurakucho Station"
    assert pois[0].category == "sights"  # not "beaches"


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
