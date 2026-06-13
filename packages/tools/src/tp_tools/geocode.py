"""Geocoding via OpenStreetMap Nominatim (keyless; requires a User-Agent)."""

from __future__ import annotations

from tp_tools._http import get_json
from tp_tools.models import GeoLocation

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


async def geocode(city: str) -> GeoLocation | None:
    """Resolve a place name to coordinates. Returns None if the place isn't found."""
    results = await get_json(
        _NOMINATIM_URL,
        params={"q": city, "format": "json", "limit": 1, "addressdetails": 1},
    )
    if not results:
        return None
    top = results[0]
    address = top.get("address") or {}
    return GeoLocation(
        name=city,
        latitude=float(top["lat"]),
        longitude=float(top["lon"]),
        display_name=top.get("display_name"),
        country=address.get("country"),
    )
