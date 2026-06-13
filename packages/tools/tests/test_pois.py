"""tp_tools.pois — mocked Overpass (no network)."""

from __future__ import annotations

import asyncio

import respx
from httpx import Response
from tp_tools.pois import find_pois

_URL = "https://overpass-api.de/api/interpreter"


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
        pois = asyncio.run(find_pois(35.0, 135.7, "temples"))
    assert len(pois) == 1
    assert pois[0].name == "Kinkaku-ji"
    assert pois[0].category == "temples"


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
        pois = asyncio.run(find_pois(35.0, 135.7, "history"))
    assert pois[0].name == "Nijo Castle"
    assert pois[0].latitude == 35.1
