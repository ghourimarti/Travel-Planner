"""tp_tools.routing — mocked OSRM (no network)."""

from __future__ import annotations

import asyncio

import respx
from httpx import Response
from tp_tools.routing import route

_URL_RE = r"https://router\.project-osrm\.org/route/v1/driving/.*"


def test_parses_legs() -> None:
    with respx.mock:
        respx.get(url__regex=_URL_RE).mock(
            return_value=Response(
                200, json={"routes": [{"legs": [{"distance": 1200.0, "duration": 300.0}]}]}
            )
        )
        legs = asyncio.run(route([("A", 35.0, 135.7), ("B", 35.02, 135.72)]))
    assert len(legs) == 1
    assert legs[0].from_name == "A"
    assert legs[0].to_name == "B"
    assert legs[0].distance_m == 1200.0
    assert legs[0].duration_s == 300.0


def test_fewer_than_two_points_returns_empty() -> None:
    assert asyncio.run(route([("A", 35.0, 135.7)])) == []
