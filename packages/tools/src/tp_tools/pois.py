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
_INTEREST_TAGS: dict[str, list[tuple[str, str | None]]] = {
    "food": [("amenity", "restaurant"), ("amenity", "cafe")],
    "temples": [("amenity", "place_of_worship")],
    "history": [("tourism", "museum"), ("historic", None)],
    "museums": [("tourism", "museum")],
    "nature": [("leisure", "park"), ("tourism", "viewpoint")],
    "nightlife": [("amenity", "bar"), ("amenity", "pub")],
    "shopping": [("shop", None)],
}


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
                category=interest.lower(),
                latitude=float(plat),
                longitude=float(plon),
                address=tags.get("addr:street"),
            )
        )
        if len(pois) >= limit:
            break
    return pois


async def _wiki_geosearch(
    lat: float, lon: float, interest: str, radius_m: int, limit: int
) -> list[POI]:
    """Nearby named places from the Wikipedia GeoSearch API (keyless, reliable)."""
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
            POI(name=name, category=interest.lower(), latitude=float(plat), longitude=float(plon))
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
