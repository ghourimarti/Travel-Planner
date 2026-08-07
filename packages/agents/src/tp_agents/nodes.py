"""Async graph nodes.

Each node degrades honestly on failure — a failed tool becomes a warning + a thinner
plan, never an unhandled 500. The compose node short-circuits (no LLM spend) when the
city couldn't be resolved.
"""

from __future__ import annotations

import asyncio
import re
from itertools import zip_longest
from typing import Any, Protocol

from pydantic import TypeAdapter
from tp_core.cache import TTL_GEOCODE, TTL_POIS, TTL_WEATHER, cache_aside
from tp_core.exceptions import ToolError
from tp_core.llm import LLMGateway, Tier
from tp_tools import find_pois, forecast, geocode
from tp_tools.models import POI, GeoLocation, WeatherDaily

from tp_agents.prompts import build_messages
from tp_agents.schemas import DayPlan, Itinerary, ItineraryItem, PlanRequest
from tp_agents.state import PlannerState

_GEO_ADAPTER: TypeAdapter[GeoLocation | None] = TypeAdapter(GeoLocation | None)
_POIS_ADAPTER = TypeAdapter(list[POI])
_WX_ADAPTER = TypeAdapter(list[WeatherDaily])


async def geocode_node(state: PlannerState) -> dict[str, Any]:
    request: PlanRequest = state["request"]
    warnings = list(state.get("warnings", []))
    try:
        geo = await cache_aside(
            f"geo:{request.city.strip().lower()}",
            TTL_GEOCODE,
            lambda: geocode(request.city),
            _GEO_ADAPTER,
        )
    except ToolError as exc:
        warnings.append("Geocoding service failed.")
        return {"geo": None, "error": f"geocode failed: {exc}", "warnings": warnings}
    if geo is None:
        warnings.append(f"Could not find a place named '{request.city}'.")
        return {"geo": None, "error": f"city not found: {request.city}", "warnings": warnings}
    return {"geo": geo}


class PoiRetriever(Protocol):
    """Structural type for a corpus retriever (tp_retrieval.Retriever fits this)."""

    async def retrieve(
        self, city: str, interests: list[str], *, tenant_id: str | None = None
    ) -> list[POI]: ...


async def _live_pois(geo: GeoLocation, request: PlanRequest, warnings: list[str]) -> list[POI]:
    async def fetch(interest: str) -> list[POI]:
        key = f"pois:{geo.latitude:.4f}:{geo.longitude:.4f}:{interest}"
        return await cache_aside(
            key, TTL_POIS, lambda: find_pois(geo.latitude, geo.longitude, interest), _POIS_ADAPTER
        )

    results = await asyncio.gather(
        *(fetch(i) for i in request.interests), return_exceptions=True
    )
    # Collect each interest's places, dropping failures. Buckets stay separate so we can
    # INTERLEAVE + dedup them below.
    buckets: list[list[POI]] = []
    for interest, result in zip(request.interests, results, strict=True):
        if isinstance(result, BaseException):
            warnings.append(f"POI lookup failed for '{interest}'.")
        else:
            buckets.append(list(result))
    return _merge_interest_buckets(buckets)


def _merge_interest_buckets(buckets: list[list[POI]]) -> list[POI]:
    """Round-robin the per-interest POI lists into one deduplicated list.

    Two problems this solves:
      • Duplicates — the Wikipedia fallback returns the SAME nearby places for every
        interest (it can't filter by interest), so naive concatenation repeats each
        place N times. We dedup by (name, rounded lat/lon).
      • Lost diversity — even with real per-interest results, concatenating then
        truncating to a few stops keeps only the FIRST interest's places (the "every
        POI is food" bug). Interleaving (one from each interest in turn) means a
        truncated itinerary still spans the requested interests.
    """
    seen: set[tuple[str, float, float]] = set()
    merged: list[POI] = []
    for tier in zip_longest(*buckets):  # round 1: first of each interest, round 2: second, …
        for poi in tier:
            if poi is None:
                continue
            fp = (poi.name.casefold(), round(poi.latitude, 4), round(poi.longitude, 4))
            if fp in seen:
                continue
            seen.add(fp)
            merged.append(poi)
    return merged


async def _live_weather(
    geo: GeoLocation, request: PlanRequest, warnings: list[str]
) -> list[WeatherDaily]:
    try:
        key = f"wx:{geo.latitude:.4f}:{geo.longitude:.4f}:{request.days}"
        return await cache_aside(
            key,
            TTL_WEATHER,
            lambda: forecast(geo.latitude, geo.longitude, days=request.days),
            _WX_ADAPTER,
        )
    except ToolError:
        warnings.append("Weather lookup failed.")
        return []


async def gather_node(
    state: PlannerState, *, retriever: PoiRetriever | None = None
) -> dict[str, Any]:
    geo = state.get("geo")
    warnings = list(state.get("warnings", []))
    if geo is None:
        return {"pois": [], "weather": [], "warnings": warnings}

    request: PlanRequest = state["request"]
    weather = await _live_weather(geo, request, warnings)

    pois: list[POI] = []
    if retriever is not None:  # the curated corpus is the primary grounding source
        try:
            pois = await retriever.retrieve(
                request.city, request.interests, tenant_id=state.get("tenant_id")
            )
        except Exception:  # resilience boundary: retrieval must never crash a run
            warnings.append("Corpus retrieval failed; falling back to live POIs.")
    if not pois:  # no retriever, or corpus empty/failed -> live-tool fallback
        pois = await _live_pois(geo, request, warnings)

    return {"pois": pois, "weather": weather, "warnings": warnings}


# A realistic day of sightseeing is a handful of stops, not a dozen. Over-packing a
# single day (especially when a multi-city trip collapses to ~1 day per city) produces
# an itinerary no traveler could actually follow, so we cap stops per day and keep only
# the most relevant POIs (retrieval order) for the plan.
_MAX_POIS_PER_DAY = 5


def _plan_pois(pois: list[POI], n_days: int) -> list[POI]:
    """The POIs that actually make it into the itinerary: the most relevant ones, capped
    at ``_MAX_POIS_PER_DAY`` per grounded day. Keeps the day plan and the map in sync."""
    if not pois or n_days < 1:
        return []
    n_days = min(n_days, len(pois))
    return pois[: n_days * _MAX_POIS_PER_DAY]


def _build_days(pois: list[POI], n_days: int) -> list[DayPlan]:
    """Distribute the grounded POIs across the requested days, deterministically.

    The structured ``days`` are derived from *real* POIs (never the free-text LLM
    output), so every map pin is a place that actually exists — the itinerary can't
    invent a stop here. POIs are trimmed to a realistic per-day load (``_plan_pois``),
    then split into balanced contiguous chunks preserving retrieval/relevance order; we
    emit only as many days as we can ground (no empty days padded out to ``n_days``).
    """
    pois = _plan_pois(pois, n_days)
    if not pois:
        return []
    n_days = min(n_days, len(pois))
    base, extra = divmod(len(pois), n_days)
    days: list[DayPlan] = []
    start = 0
    for d in range(n_days):
        size = base + (1 if d < extra else 0)  # front-load the remainder
        chunk = pois[start : start + size]
        start += size
        days.append(
            DayPlan(
                day=d + 1,
                items=[
                    ItineraryItem(
                        name=p.name,
                        category=p.category,
                        latitude=p.latitude,
                        longitude=p.longitude,
                        note=p.address,
                    )
                    for p in chunk
                ],
            )
        )
    return days


# --- Structural grounding ---------------------------------------------------------------
# The itinerary's named places come ONLY from the deterministic day skeleton below (real
# POIs). The LLM writes place-name-free connective prose; a guard validates that prose and
# falls back to a template if it slips in an ungrounded venue — so the final summary can
# never name a place that isn't a real, retrieved POI (the LLM critic is a second layer).
# Only multi-word / hyphenated names are candidates, so single Title-case words (the city,
# "Morning") are never flagged.
_VENUE_RE = re.compile(r"\b[A-Z][\w']*(?:[ -][A-Z][\w']*|-[a-z][\w']*)+\b")
_VENUE_STOPWORDS = frozenset(
    {"Old Town", "City Center", "City Centre", "Old City", "City Walls", "Day One", "Day Two"}
)


def _ungrounded_venues(text: str, allowed_names: list[str], city: str) -> list[str]:
    """Venue-shaped proper nouns in ``text`` that aren't a known real place.

    A candidate is cleared if it appears (case-insensitively) inside an allowed POI name
    or the city; otherwise it is an ungrounded mention the prose must not keep.
    """
    hay = " ".join([*allowed_names, city]).casefold()
    return [
        m.group(0)
        for m in _VENUE_RE.finditer(text)
        if m.group(0) not in _VENUE_STOPWORDS and m.group(0).casefold() not in hay
    ]


def _fallback_intro(request: PlanRequest, *, grounded: bool) -> str:
    """Deterministic, place-name-free intro used when the LLM prose can't be trusted."""
    if not grounded:
        return (
            f"A short guide to {request.city}. We couldn't ground specific stops for your "
            "interests, so this plan stays general — please verify details locally."
        )
    kinds = ", ".join(request.interests)
    return (
        f"A {request.days}-day plan for {request.city} focused on {kinds}. The stops below "
        "are real places matched to your interests — pace yourself and check opening hours."
    )


def _render_summary(intro: str, days: list[DayPlan]) -> str:
    """Grounded skeleton: the (validated) LLM intro + real-POI bullets, one section per day."""
    parts: list[str] = [intro.strip()] if intro.strip() else []
    for day in days:
        parts.append(f"\n### Day {day.day}")
        for item in day.items:
            note = f" — {item.note}" if item.note else ""
            parts.append(f"- **{item.name}** ({item.category}){note}")
    return "\n".join(parts).strip()


async def compose_node(state: PlannerState, gateway: LLMGateway) -> dict[str, Any]:
    request: PlanRequest = state["request"]
    warnings = list(state.get("warnings", []))
    geo = state.get("geo")
    pois = list(state.get("pois", []))
    weather = list(state.get("weather", []))
    attempts = state.get("compose_attempts", 0) + 1

    if geo is None:
        itinerary = Itinerary(
            city=request.city,
            summary_markdown=(
                f"We couldn't find a place named **{request.city}**, so no itinerary could be "
                "created. Please check the spelling or try a nearby city."
            ),
            warnings=warnings,
            grounded=False,
        )
        return {"itinerary": itinerary, "compose_attempts": attempts}

    # The itinerary builder owns honesty about its own (possibly degraded) input —
    # so this warning fires wherever compose runs, not only via gather_node (e.g. eval).
    if not pois:
        warnings.append("No POIs available; the itinerary is limited to general guidance.")

    # On a corrective re-compose, feed the critic's specific issues back into the prompt.
    revision: str | None = None
    verdict = state.get("critic_verdict")
    if attempts > 1 and verdict is not None and verdict.has_issues:
        parts: list[str] = []
        if verdict.invented_places:
            parts.append(f"Remove places not in the list: {', '.join(verdict.invented_places)}.")
        parts.extend(verdict.issues)
        revision = " ".join(parts)

    messages = build_messages(request, pois, weather, revision=revision)
    response = await gateway.complete(messages, Tier.MID, max_tokens=400)
    prior_cost = state["itinerary"].cost_usd if attempts > 1 and state.get("itinerary") else 0.0

    days = _build_days(pois, request.days)
    # Structural grounding: keep the LLM prose only if it names no ungrounded venue, else use
    # a template. All named venues then come solely from the deterministic day skeleton.
    intro = response.text.strip()
    if not intro or _ungrounded_venues(intro, [p.name for p in pois], request.city):
        intro = _fallback_intro(request, grounded=bool(pois))

    itinerary = Itinerary(
        city=request.city,
        summary_markdown=_render_summary(intro, days),
        days=days,
        pois_used=_plan_pois(pois, request.days) or pois,
        weather=weather,
        warnings=warnings,
        grounded=bool(pois),
        cost_usd=round(response.usage.cost_usd + prior_cost, 6),
        corrections=attempts - 1,
        center=geo,
    )
    return {"itinerary": itinerary, "compose_attempts": attempts}
