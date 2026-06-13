"""POI search via the OpenStreetMap Overpass API (keyless)."""

from __future__ import annotations

from tp_tools._http import get_json
from tp_tools.models import POI

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Coarse interest -> OSM tag selectors. (key, None) matches any value of that key.
_INTEREST_TAGS: dict[str, list[tuple[str, str | None]]] = {
    "food": [("amenity", "restaurant"), ("amenity", "cafe")],
    "temples": [("amenity", "place_of_worship")],
    "history": [("tourism", "museum"), ("historic", None)],
    "museums": [("tourism", "museum")],
    "nature": [("leisure", "park"), ("tourism", "viewpoint")],
    "nightlife": [("amenity", "bar"), ("amenity", "pub")],
    "shopping": [("shop", None)],
}


def _build_query(lat: float, lon: float, interest: str, radius_m: int, limit: int) -> str:
    tags = _INTEREST_TAGS.get(interest.lower(), [("tourism", "attraction")])
    clauses = ""
    for key, val in tags:
        selector = f'["{key}"]' if val is None else f'["{key}"="{val}"]'
        clauses += f"node{selector}(around:{radius_m},{lat},{lon});"
    return f"[out:json][timeout:25];({clauses});out center {limit};"


async def find_pois(
    lat: float,
    lon: float,
    interest: str,
    *,
    radius_m: int = 3000,
    limit: int = 15,
    endpoint: str = _OVERPASS_URL,
) -> list[POI]:
    """Find named POIs near a point matching a coarse interest category.

    ``endpoint`` is injectable because public Overpass mirrors vary in
    availability (the canonical overpass-api.de WAF-blocks some clients).
    Production should self-host Overpass or use a paid POI provider.
    """
    query = _build_query(lat, lon, interest, radius_m, limit)
    data = await get_json(
        endpoint,
        params={"data": query},
        headers={"Accept": "application/json"},
    )
    pois: list[POI] = []
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        center = element.get("center") or {}
        plat = element.get("lat", center.get("lat"))
        plon = element.get("lon", center.get("lon"))
        if plat is None or plon is None:
            continue
        pois.append(
            POI(
                name=name,
                category=interest.lower(),
                latitude=float(plat),
                longitude=float(plon),
                address=tags.get("addr:street"),
            )
        )
        if len(pois) >= limit:
            break
    return pois
