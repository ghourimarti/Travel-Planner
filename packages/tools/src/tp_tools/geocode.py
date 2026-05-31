"""Geocoding: city name -> coordinates (Open-Meteo geocoding API, no key)."""

from __future__ import annotations

from typing import Any

from tp_tools._http import ToolError, fetch_json
from tp_tools.models import GeoLocation

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"


async def geocode_city(name: str) -> GeoLocation:
    """Resolve a city/place name to its top matching coordinates."""
    payload: Any = await fetch_json(
        "GET",
        _GEOCODE_URL,
        params={"name": name, "count": 1, "language": "en", "format": "json"},
    )
    results = payload.get("results") or []
    if not results:
        raise ToolError(f"no geocoding result for {name!r}")
    top = results[0]
    return GeoLocation(
        name=top.get("name", name),
        latitude=float(top["latitude"]),
        longitude=float(top["longitude"]),
        country=top.get("country"),
    )
