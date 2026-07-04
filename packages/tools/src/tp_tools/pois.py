"""POI search via OpenStreetMap Overpass (keyless), with a reliable Wikipedia fallback.

Public Overpass mirrors are effectively unusable (``overpass-api.de`` WAF-blocks
with HTTP 406; the rest rate-limit, go slow, or are unreachable), so we DON'T try
them by default — that only adds latency and log noise before failing. Instead:
  • Overpass is used ONLY when you point ``OVERPASS_URL`` (or the ``endpoint`` arg)
    at a reachable instance (self-hosted in production for interest-filtered POIs),
    with an HTTP timeout LONGER than the Overpass query's own ``[timeout:N]``;
  • otherwise (and whenever Overpass fails or returns empty) we use the Wikipedia
    GeoSearch API — keyless, globally reachable, same Wikimedia infra as geocoding —
    so the itinerary is still grounded in real, named, geo-located places.
"""

from __future__ import annotations

import os

from tp_core.exceptions import NonRetryableToolError, RetryableToolError

from tp_tools._http import get_json
from tp_tools.models import POI

# A sensible default to put in OVERPASS_URL if you self-host or find a working mirror.
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

_QUERY_TIMEOUT_S = 20  # Overpass-side budget (must be < the HTTP timeout below)
_HTTP_TIMEOUT_S = 30.0  # client read budget — strictly greater than _QUERY_TIMEOUT_S

# Reliable, keyless fallback when Overpass is unreachable/empty.
_WIKI_API = "https://en.wikipedia.org/w/api.php"
_WIKI_MAX_RADIUS_M = 10000  # GeoSearch hard cap

# Coarse interest -> OSM tag selectors. (key, None) matches any value of that key.
# Covers the full interest vocabulary the planner accepts, so every requested interest
# maps to a real, category-appropriate Overpass query (not a generic "attraction" fallback).
_INTEREST_TAGS: dict[str, list[tuple[str, str | None]]] = {
    "food": [("amenity", "restaurant"), ("amenity", "cafe"), ("amenity", "fast_food")],
    "temples": [("amenity", "place_of_worship"), ("building", "temple")],
    "history": [("historic", None), ("tourism", "museum")],
    "museums": [("tourism", "museum"), ("tourism", "gallery")],
    "art": [("tourism", "gallery"), ("tourism", "artwork"), ("amenity", "arts_centre")],
    "architecture": [
        ("building", "cathedral"),
        ("historic", "monument"),
        ("tourism", "attraction"),
    ],
    "nature": [("leisure", "park"), ("tourism", "viewpoint"), ("boundary", "national_park")],
    "beaches": [("natural", "beach"), ("leisure", "beach_resort")],
    "nightlife": [("amenity", "bar"), ("amenity", "pub"), ("amenity", "nightclub")],
    "shopping": [("shop", "mall"), ("shop", "department_store"), ("shop", "marketplace")],
}

# When Overpass returns a place, its own OSM tags tell us what it *actually* is — far
# better than assuming it matches the interest we searched for. This maps the tag we
# matched on back to a human category for display/grouping.
_TAG_CATEGORY: dict[tuple[str, str | None], str] = {
    ("amenity", "restaurant"): "food",
    ("amenity", "cafe"): "food",
    ("amenity", "fast_food"): "food",
    ("amenity", "place_of_worship"): "temples",
    ("building", "temple"): "temples",
    ("building", "cathedral"): "architecture",
    ("historic", "monument"): "architecture",
    ("historic", None): "history",
    ("tourism", "museum"): "museums",
    ("tourism", "gallery"): "art",
    ("tourism", "artwork"): "art",
    ("amenity", "arts_centre"): "art",
    ("leisure", "park"): "nature",
    ("tourism", "viewpoint"): "nature",
    ("boundary", "national_park"): "nature",
    ("natural", "beach"): "beaches",
    ("leisure", "beach_resort"): "beaches",
    ("amenity", "bar"): "nightlife",
    ("amenity", "pub"): "nightlife",
    ("amenity", "nightclub"): "nightlife",
    ("shop", "mall"): "shopping",
    ("shop", "department_store"): "shopping",
    ("shop", "marketplace"): "shopping",
    ("tourism", "attraction"): "sights",
}


def _category_from_tags(tags: dict[str, object], interest: str) -> str:
    """Best real category for a place from its own OSM tags, falling back to the
    searched interest. A restaurant tagged ``amenity=restaurant`` reads as 'food'
    even if we found it under a broad query."""
    for (key, val), category in _TAG_CATEGORY.items():
        if key in tags and (val is None or tags.get(key) == val):
            return category
    return interest.lower()


def _endpoints(endpoint: str | None) -> list[str]:
    """Overpass endpoints to try: explicit arg, else OVERPASS_URL, else none.

    Public mirrors are NOT tried by default — they reliably fail and just add
    latency + noise before the Wikipedia fallback. Set OVERPASS_URL to opt in.
    """
    if endpoint is not None:
        return [endpoint]
    env = os.environ.get("OVERPASS_URL")
    return [env] if env else []


def _build_query(lat: float, lon: float, interest: str, radius_m: int, limit: int) -> str:
    tags = _INTEREST_TAGS.get(interest.lower(), [("tourism", "attraction")])
    clauses = ""
    for key, val in tags:
        selector = f'["{key}"]' if val is None else f'["{key}"="{val}"]'
        clauses += f"node{selector}(around:{radius_m},{lat},{lon});"
    return f"[out:json][timeout:{_QUERY_TIMEOUT_S}];({clauses});out center {limit};"


def _parse(data: object, interest: str, limit: int) -> list[POI]:
    pois: list[POI] = []
    elements = data.get("elements", []) if isinstance(data, dict) else []
    for element in elements:
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
                # Real category from the place's own OSM tags, not just the search interest.
                category=_category_from_tags(tags, interest),
                latitude=float(plat),
                longitude=float(plon),
                address=tags.get("addr:street"),
            )
        )
        if len(pois) >= limit:
            break
    return pois


# Wikipedia GeoSearch returns "nearby articles" by distance only — it CANNOT filter by
# interest. So the same articles come back for every interest. Labeling them with the
# searched interest (the old behavior) was a lie: it made 10 identical result sets look
# like 10 different interest categories, and truncation then kept only the first. We label
# these honestly as "sights" — real, named, geolocated places, category unverified — and
# dedup across interests upstream so the itinerary shows distinct places, not repeats.
_WIKI_FALLBACK_CATEGORY = "sights"


async def _wiki_geosearch(
    lat: float, lon: float, interest: str, radius_m: int, limit: int
) -> list[POI]:
    """Nearby named places from the Wikipedia GeoSearch API (keyless, reliable).

    Note: GeoSearch ranks purely by distance and has no interest/category filter, so
    ``interest`` does not shape the query and the results are labeled generically.
    """
    radius = min(max(radius_m, 10), _WIKI_MAX_RADIUS_M)
    data = await get_json(
        _WIKI_API,
        params={
            "action": "query",
            "format": "json",
            "list": "geosearch",
            "gscoord": f"{lat}|{lon}",
            "gsradius": str(radius),
            "gslimit": str(min(limit, 50)),
        },
        headers={"Accept": "application/json"},
        timeout=_HTTP_TIMEOUT_S,
    )
    results = data.get("query", {}).get("geosearch", []) if isinstance(data, dict) else []
    pois: list[POI] = []
    for item in results:
        name = item.get("title")
        plat = item.get("lat")
        plon = item.get("lon")
        if not name or plat is None or plon is None:
            continue
        pois.append(
            POI(
                name=name,
                category=_WIKI_FALLBACK_CATEGORY,
                latitude=float(plat),
                longitude=float(plon),
            )
        )
        if len(pois) >= limit:
            break
    return pois


async def find_pois(
    lat: float,
    lon: float,
    interest: str,
    *,
    radius_m: int = 3000,
    limit: int = 15,
    endpoint: str | None = None,
) -> list[POI]:
    """Find named POIs near a point matching a coarse interest category.

    Tries each Overpass endpoint (``OVERPASS_URL`` override, then public mirrors)
    and returns the first non-empty result. If every Overpass endpoint fails or
    returns nothing, falls back to Wikipedia GeoSearch so the itinerary is still
    grounded in real places. Raises only if both Overpass and the fallback fail.
    """
    query = _build_query(lat, lon, interest, radius_m, limit)
    last_error: Exception | None = None
    for ep in _endpoints(endpoint):
        try:
            data = await get_json(
                ep,
                params={"data": query},
                headers={"Accept": "application/json"},
                timeout=_HTTP_TIMEOUT_S,
            )
        except (RetryableToolError, NonRetryableToolError) as exc:
            last_error = exc
            continue
        pois = _parse(data, interest, limit)
        if pois:
            return pois
        break  # Overpass answered but empty — go straight to the reliable fallback

    try:  # reliable, globally-reachable fallback
        fallback = await _wiki_geosearch(lat, lon, interest, radius_m, limit)
        if fallback:
            return fallback
    except (RetryableToolError, NonRetryableToolError) as exc:
        last_error = last_error or exc

    if last_error is not None:
        raise last_error
    return []
