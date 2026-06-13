"""Routing via OSRM (keyless public server)."""

from __future__ import annotations

from tp_tools._http import get_json
from tp_tools.models import RouteLeg

_OSRM_URL = "https://router.project-osrm.org/route/v1/driving"


async def route(points: list[tuple[str, float, float]]) -> list[RouteLeg]:
    """Per-leg distance/duration for an ordered list of ``(name, lat, lon)`` points.

    Note: legs follow the given order — choosing a good order is the agent's job (S7).
    """
    if len(points) < 2:
        return []
    coords = ";".join(f"{lon},{lat}" for _name, lat, lon in points)
    data = await get_json(f"{_OSRM_URL}/{coords}", params={"overview": "false", "steps": "false"})
    routes = data.get("routes") or []
    if not routes:
        return []
    legs = routes[0].get("legs", [])
    out: list[RouteLeg] = []
    for i, leg in enumerate(legs):
        if i + 1 >= len(points):
            break
        out.append(
            RouteLeg(
                from_name=points[i][0],
                to_name=points[i + 1][0],
                distance_m=float(leg.get("distance", 0.0)),
                duration_s=float(leg.get("duration", 0.0)),
            )
        )
    return out
