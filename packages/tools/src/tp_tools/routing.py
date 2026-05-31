"""Travel-time/distance matrix between coordinates (OSRM table service, no key).

NOTE: OSRM expects ``lon,lat`` order — the classic footgun handled here so callers
can pass natural ``(lat, lon)`` tuples everywhere.
"""

from __future__ import annotations

from typing import Any

from tp_tools._http import ToolError, fetch_json
from tp_tools.models import RouteMatrix

_OSRM_URL = "https://router.project-osrm.org/table/v1/driving/"


async def route_matrix(coords: list[tuple[float, float]]) -> RouteMatrix:
    """Pairwise driving durations (s) and distances (m) between ``(lat, lon)`` points."""
    if len(coords) < 2:
        raise ToolError("route_matrix needs at least 2 coordinates")

    # OSRM wants lon,lat
    coord_str = ";".join(f"{lon},{lat}" for lat, lon in coords)
    payload: Any = await fetch_json(
        "GET",
        f"{_OSRM_URL}{coord_str}",
        params={"annotations": "duration,distance"},
    )
    if payload.get("code") != "Ok":
        raise ToolError(f"OSRM error: {payload.get('code')}")
    return RouteMatrix(
        durations_s=payload["durations"],
        distances_m=payload["distances"],
    )
