"""Geocoding via OpenStreetMap Nominatim (keyless; requires a User-Agent)."""

from __future__ import annotations

from typing import Any

from tp_core.exceptions import UpstreamRateLimitedError
from tp_core.llm.circuit import BreakerState, infra_breaker
from tp_core.throttle import acquire_slot

from tp_tools._http import get_json
from tp_tools.models import GeoLocation

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

#: Public Nominatim's usage policy: at most ONE request per second - for the whole app,
#: not per process or per tenant. Enforced through a shared slot (tp_core.throttle).
_NOMINATIM = "nominatim"
_NOMINATIM_INTERVAL_S = 1.0
#: How long a lookup may wait for its turn before it gives up as "busy". Only uncached
#: places ever wait: a cached city never reaches this function.
_NOMINATIM_MAX_WAIT_S = 15.0

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

#: OSM classes that are never a travel destination. When NO candidate is a settlement,
#: the old fallback trusted result #1 whatever it was, so a typo became a confident
#: itinerary anchored on infrastructure. Measured live against Nominatim:
#:
#:     Kyot          -> amenity/studio      "KYOT-TV Cable Channel 21" (US)
#:     Pariss        -> highway/residential "Pariss Lane" (US)
#:     Kyoto, Osaka  -> highway/primary     a road between the two cities
#:
#: A DENY list, not an allow list, on purpose: a result with an unknown or missing
#: class keeps the old behaviour, so this can only turn a wrong anchor into an honest
#: "not found" - never a real destination into a refusal.
_NOT_A_DESTINATION = frozenset({
    "highway", "amenity", "building", "shop", "office", "craft", "man_made",
    "railway", "aeroway", "emergency", "healthcare", "power", "public_transport",
    "telecom",
})

#: Below this Nominatim importance a match is an obscure place, and the plan says so.
#: NOT a rejection threshold: measured, a real destination can sit exactly where a typo
#: lands - `Hallstatt` and `kyota` (a village in Uganda) both score 0.147 - so refusing
#: on importance would turn away genuine trips. Warning is the honest middle: the plan
#: is still made, but "Planned for Kyota, Uganda" is on screen instead of silent.
LOW_PROMINENCE_IMPORTANCE = 0.25


def _prefers_settlement(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the first settlement; else the first plausible destination; else nothing.

    The middle step matters: for a query that genuinely has no `place` match (a
    landmark someone typed as a destination, a national park) the old behaviour is
    preserved. Only a candidate list made entirely of infrastructure now returns None.
    """
    for r in results:
        if r.get("class") == "place":
            return r
    for r in results:
        if r.get("class") == "boundary" and r.get("type") == "administrative":
            return r
    for r in results:
        if r.get("class") not in _NOT_A_DESTINATION:
            return r
    return None


def is_low_prominence(geo: GeoLocation) -> bool:
    """True when the match is an obscure place - worth a visible warning, not a refusal."""
    return geo.importance is not None and geo.importance < LOW_PROMINENCE_IMPORTANCE


async def geocode(city: str) -> GeoLocation | None:
    """Resolve a place name to coordinates. Returns None if the place isn't found.

    Three guards, because Nominatim is a shared public service with a hard usage policy
    and it refused this deployment for ~20 minutes after one burst (2026-09-30):
    a breaker (after repeated failures, stop calling for a cooldown), an app-wide slot
    (<= 1 request/s), and no retry on 429 (tp_tools._http). Only uncached places get
    here: known cities - and, now, known NON-places - are answered from the cache.
    """
    breaker = infra_breaker(_NOMINATIM)
    if breaker.state(_NOMINATIM) is BreakerState.OPEN:  # read-only: no probe claimed
        raise UpstreamRateLimitedError(f"{_NOMINATIM}: paused after repeated failures")
    await acquire_slot(
        _NOMINATIM, interval_s=_NOMINATIM_INTERVAL_S, max_wait_s=_NOMINATIM_MAX_WAIT_S
    )
    # Claimed only AFTER the slot, so a half-open probe is always followed by a call and
    # its outcome is always recorded - a probe claimed and then abandoned would wedge it.
    if not breaker.allows(_NOMINATIM):
        raise UpstreamRateLimitedError(f"{_NOMINATIM}: another caller is probing it")
    ok = False
    try:
        results = await get_json(
            _NOMINATIM_URL,
            params={
                "q": city,
                "format": "json",
                "limit": _CANDIDATES,
                "addressdetails": 1,
                # Output language only - matching is unaffected. Without it names come
                # back in the local script ("日本", "پاکستان"), which the UI then shows.
                "accept-language": "en",
            },
        )
        ok = True
    finally:
        if ok:
            breaker.record_success(_NOMINATIM)
        else:
            breaker.record_failure(_NOMINATIM)
    if not results:
        return None
    top = _prefers_settlement(results)
    if top is None:  # only roads / buildings / amenities matched: not a destination
        return None
    address = top.get("address") or {}
    importance = top.get("importance")
    return GeoLocation(
        name=city,
        latitude=float(top["lat"]),
        longitude=float(top["lon"]),
        display_name=top.get("display_name"),
        country=address.get("country"),
        importance=float(importance) if importance is not None else None,
        kind=top.get("addresstype") or top.get("type"),
    )
