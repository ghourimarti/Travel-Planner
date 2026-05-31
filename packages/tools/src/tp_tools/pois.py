"""Point-of-interest search over OpenStreetMap via the Overpass API (no key).

Maps free-text interests to OSM tag filters, queries nodes/ways/relations within
a radius, and returns named POIs. Provider-swappable (e.g. Google Places) behind
the same ``search_pois`` contract.
"""

from __future__ import annotations

from typing import Any

from tp_tools._http import fetch_json
from tp_tools.models import POI

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# interest -> list of (osm_key, osm_value); value "*" means "key present, any value".
INTEREST_TAGS: dict[str, list[tuple[str, str]]] = {
    "art": [("tourism", "museum"), ("tourism", "gallery")],
    "museum": [("tourism", "museum")],
    "museums": [("tourism", "museum")],
    "history": [("historic", "*")],
    "historic": [("historic", "*")],
    "food": [("amenity", "restaurant")],
    "restaurants": [("amenity", "restaurant")],
    "cafe": [("amenity", "cafe")],
    "coffee": [("amenity", "cafe")],
    "nature": [("leisure", "park")],
    "parks": [("leisure", "park")],
    "nightlife": [("amenity", "bar"), ("amenity", "pub")],
    "shopping": [("shop", "mall"), ("shop", "department_store")],
    "sightseeing": [("tourism", "attraction"), ("tourism", "viewpoint")],
    "landmarks": [("tourism", "attraction"), ("historic", "monument")],
}
_DEFAULT_TAGS: list[tuple[str, str]] = [("tourism", "attraction")]
_CATEGORY_KEYS = ("tourism", "amenity", "historic", "leisure", "shop")


def _build_query(
    latitude: float, longitude: float, interests: list[str], radius_m: int, limit: int
) -> str:
    clauses: list[str] = []
    seen: set[tuple[str, str]] = set()
    for interest in interests:
        for key, value in INTEREST_TAGS.get(interest.lower().strip(), _DEFAULT_TAGS):
            if (key, value) in seen:
                continue
            seen.add((key, value))
            selector = f'["{key}"]' if value == "*" else f'["{key}"="{value}"]'
            clauses.append(f"nwr{selector}(around:{radius_m},{latitude},{longitude});")
    if not clauses:
        clauses.append(f'nwr["tourism"="attraction"](around:{radius_m},{latitude},{longitude});')
    body = "".join(clauses)
    return f"[out:json][timeout:25];({body});out center {limit};"


def _category_of(tags: dict[str, Any]) -> str:
    for key in _CATEGORY_KEYS:
        if key in tags:
            return f"{key}:{tags[key]}"
    return "poi"


async def search_pois(
    latitude: float,
    longitude: float,
    interests: list[str],
    *,
    radius_m: int = 4000,
    limit: int = 30,
) -> list[POI]:
    """Find named POIs matching ``interests`` within ``radius_m`` of a point."""
    query = _build_query(latitude, longitude, interests, radius_m, limit)
    payload: Any = await fetch_json("POST", _OVERPASS_URL, data={"data": query})

    pois: list[POI] = []
    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        name = tags.get("name")
        if not name:
            continue
        center = element.get("center") or {}
        lat = element.get("lat", center.get("lat"))
        lon = element.get("lon", center.get("lon"))
        if lat is None or lon is None:
            continue
        pois.append(
            POI(
                name=name,
                category=_category_of(tags),
                latitude=float(lat),
                longitude=float(lon),
            )
        )
    return pois
