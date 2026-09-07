"""Multi-city coordinator: fan out the city worker, merge, add inter-city legs.

Orchestrator-worker pattern: each city runs the worker+critic subgraph in PARALLEL;
failures are isolated (partial results) so one bad city never sinks the trip;
consecutive city centers are routed for inter-city transitions.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import TypeAdapter
from tp_core.cache import TTL_ROUTE, cache_aside
from tp_core.llm import LLMGateway
from tp_core.settings import DEFAULT_MAX_COST_USD
from tp_core.tracing import get_tracer
from tp_tools import route
from tp_tools.models import RouteLeg

from tp_agents.checkpoint import make_checkpointer
from tp_agents.graph import build_planner_graph, run_graph, stream_graph
from tp_agents.nodes import PoiRetriever
from tp_agents.schemas import Itinerary, PlanRequest, TripItinerary, TripRequest
from tp_agents.state import PlannerState

# Honor the requested trip length (≤10 days over ≤5 cities). The real per-city day count is
# bounded by how many POIs we can ground (_build_days caps days at len(pois)), so a thin
# corpus degrades to fewer days honestly rather than padding empty ones.
_MAX_DAYS_PER_CITY = 10
_MAX_COMPOSE_ATTEMPTS = 2
_ROUTE_ADAPTER = TypeAdapter(list[RouteLeg])


async def _inter_city_legs(cities: list[Itinerary]) -> list[RouteLeg]:
    points = [
        (c.city, c.center.latitude, c.center.longitude) for c in cities if c.center is not None
    ]
    if len(points) < 2:
        return []
    key = "route:" + "|".join(f"{c}:{lat:.4f}:{lon:.4f}" for c, lat, lon in points)
    try:
        return await cache_aside(key, TTL_ROUTE, lambda: route(points), _ROUTE_ADAPTER)
    except Exception:  # routing is best-effort; a trip without legs still ships
        return []


def _merge_summary(cities: list[Itinerary], legs: list[RouteLeg]) -> str:
    leg_by_pair = {(leg.from_name, leg.to_name): leg for leg in legs}
    names = ", ".join(c.city for c in cities)
    parts: list[str] = [f"# {len(cities)}-city trip: {names}\n"]
    for i, city in enumerate(cities):
        parts.append(f"## {city.city}\n\n{city.summary_markdown}\n")
        if i + 1 < len(cities):
            leg = leg_by_pair.get((city.city, cities[i + 1].city))
            if leg is not None:
                hop = f"~{leg.distance_m / 1000:.0f} km, ~{leg.duration_s / 3600:.1f} h by road"
                parts.append(f"\n**{city.city} → {cities[i + 1].city}:** {hop}\n")
    return "\n".join(parts)


async def plan_trip(
    request: TripRequest,
    *,
    gateway: LLMGateway | None = None,
    retriever: PoiRetriever | None = None,
    run_id: str | None = None,
    tenant_id: str | None = None,
    on_event: Callable[..., Awaitable[None]] | None = None,
) -> TripItinerary:
    """Plan a multi-city trip: parallel per-city workers + partial results + inter-city legs.

    With ``run_id`` each city is checkpointed under ``"{run_id}:{city}"`` (its own
    checkpointer to stay concurrency-safe), so on a worker crash a finished city resumes
    from END (≈ free) and only an unfinished city replays mid-graph. ``on_event``
    streams a per-node progress event tagged with its city.
    """
    gw = gateway or LLMGateway.from_settings()
    days_each = min(_MAX_DAYS_PER_CITY, max(1, request.days // len(request.cities)))

    async def run_city(city: str) -> Itinerary:
        sub = PlanRequest(city=city, interests=request.interests, days=days_each)
        thread = f"{run_id}:{city}" if run_id is not None else None
        initial: PlannerState = {
            "request": sub,
            "warnings": [],
            "max_compose_attempts": _MAX_COMPOSE_ATTEMPTS,
            "max_cost_usd": DEFAULT_MAX_COST_USD,
            "tenant_id": tenant_id,
        }
        async with make_checkpointer(thread) as cp:
            graph = build_planner_graph(gw, retriever, checkpointer=cp)
            if on_event is not None and cp is not None:

                async def city_event(node: str, delta: Any) -> None:
                    await on_event(node, delta, city=city)

                final: PlannerState = await stream_graph(graph, cp, thread, initial, city_event)
            else:
                final = await run_graph(graph, cp, thread, initial)
        itinerary: Itinerary = final["itinerary"]
        return itinerary

    with get_tracer().start_as_current_span("trip.plan") as span:
        span.set_attribute("run.id", run_id or "sync")
        span.set_attribute("trip.cities_requested", len(request.cities))
        results = await asyncio.gather(
            *(run_city(c) for c in request.cities), return_exceptions=True
        )

        city_itins: list[Itinerary] = []
        warnings: list[str] = []
        failed: list[str] = []
        for city, res in zip(request.cities, results, strict=True):
            if isinstance(res, BaseException):
                failed.append(city)
                warnings.append(f"Planning failed for {city}; it was left out of the trip.")
            else:
                city_itins.append(res)
                warnings.extend(res.warnings)
                if not res.grounded:
                    warnings.append(f"{city}: limited plan (no grounded POIs found).")

        legs = await _inter_city_legs(city_itins)
        trip = TripItinerary(
            summary_markdown=_merge_summary(city_itins, legs),
            cities=city_itins,
            inter_city_legs=legs,
            failed_cities=failed,
            warnings=warnings,
            cost_usd=round(sum(c.cost_usd for c in city_itins), 6),
            venues=sorted({v for c in city_itins for v in c.venues}),
        )
        span.set_attribute("trip.cities_succeeded", len(city_itins))
        span.set_attribute("trip.cities_failed", len(failed))
        span.set_attribute("trip.partial", bool(failed))
        span.set_attribute("trip.cost_usd", trip.cost_usd)
        return trip
