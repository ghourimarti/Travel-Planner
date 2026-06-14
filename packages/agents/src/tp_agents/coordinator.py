"""Multi-city coordinator (S8): fan out the city worker, merge, add inter-city legs.

Orchestrator-worker pattern (Decision 3): each city runs the S7 worker+critic
subgraph in PARALLEL; failures are isolated (partial results) so one bad city never
sinks the trip; consecutive city centers are routed for inter-city transitions.
"""

from __future__ import annotations

import asyncio

from tp_core.llm import LLMGateway
from tp_tools import route
from tp_tools.models import RouteLeg

from tp_agents.checkpoint import make_checkpointer
from tp_agents.graph import build_planner_graph, run_graph
from tp_agents.nodes import PoiRetriever
from tp_agents.schemas import Itinerary, PlanRequest, TripItinerary, TripRequest
from tp_agents.state import PlannerState

_MAX_DAYS_PER_CITY = 3
_MAX_COMPOSE_ATTEMPTS = 2


async def _inter_city_legs(cities: list[Itinerary]) -> list[RouteLeg]:
    points = [
        (c.city, c.center.latitude, c.center.longitude) for c in cities if c.center is not None
    ]
    if len(points) < 2:
        return []
    try:
        return await route(points)
    except Exception:  # routing is best-effort; degrade to no legs (Decision 21)
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
) -> TripItinerary:
    """Plan a multi-city trip: parallel per-city workers + partial results + inter-city legs.

    With ``run_id`` each city is checkpointed under ``"{run_id}:{city}"`` (its own
    checkpointer to stay concurrency-safe), so on a worker crash a finished city resumes
    from END (≈ free) and only an unfinished city replays mid-graph (S9b).
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
        }
        async with make_checkpointer(thread) as cp:
            graph = build_planner_graph(gw, retriever, checkpointer=cp)
            final: PlannerState = await run_graph(graph, cp, thread, initial)
        itinerary: Itinerary = final["itinerary"]
        return itinerary

    results = await asyncio.gather(*(run_city(c) for c in request.cities), return_exceptions=True)

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
    return TripItinerary(
        summary_markdown=_merge_summary(city_itins, legs),
        cities=city_itins,
        inter_city_legs=legs,
        failed_cities=failed,
        warnings=warnings,
        cost_usd=round(sum(c.cost_usd for c in city_itins), 6),
    )
