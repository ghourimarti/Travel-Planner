"""Geocoding via OpenStreetMap Nominatim (keyless; requires a User-Agent)."""

from __future__ import annotations

from typing import Any

from tp_tools._http import get_json
from tp_tools.models import GeoLocation

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

#: How many candidates to ask Nominatim for before choosing.
#:
#: This used to be 1, and result #1 was trusted unconditionally. That produced a
#: confident two-day Washington DC itinerary labelled "Nara": Nominatim's top hit for
#: the bare string `Nara` is NARA, the US National Archives and Records Administration,
#: at 38.8927,-77.0229. Retrieval then did its job perfectly around those coordinates,
#: `_build_days()` grounded every item in genuinely retrieved POIs, and the run came
#: back `grounded=True` with `warnings=[]`.
#:
#: The lesson worth keeping: structural grounding protects against FABRICATION, not
#: against a wrong ANCHOR. Nothing downstream can notice, because nothing downstream
#: knows where the user meant. Only the geocoder can.
_CANDIDATES = 5

#: OSM `class` values that denote a populated place rather than a building or office.
#: `place` covers city/town/village/hamlet/suburb; `boundary` + type `administrative`
#: covers municipalities that are mapped as areas rather than points.
_PLACE_CLASSES = ("place", "boundary")


def _prefers_settlement(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick the first result that looks like a settlement, else fall back to #1.

    The fallback matters: for a query that genuinely has no `place` match (a district,
    a landmark someone typed as a destination), the old behaviour is preserved exactly.
    This can only ever change the answer when a settlement candidate exists and was
    being passed over.
    """
    for r in results:
        if r.get("class") == "place":
            return r
    for r in results:
        if r.get("class") == "boundary" and r.get("type") == "administrative":
            return r
    return results[0]


async def geocode(city: str) -> GeoLocation | None:
    """Resolve a place name to coordinates. Returns None if the place isn't found."""
    results = await get_json(
        _NOMINATIM_URL,
        params={
            "q": city,
            "format": "json",
            "limit": _CANDIDATES,
            "addressdetails": 1,
        },
    )
    if not results:
        return None
    top = _prefers_settlement(results)
    address = top.get("address") or {}
    return GeoLocation(
        name=city,
        latitude=float(top["lat"]),
        longitude=float(top["lon"]),
        display_name=top.get("display_name"),
        country=address.get("country"),
    )
