"""LangGraph state for the city planner.

Kept to serializable values (Pydantic models + builtins) so the checkpointer can
persist and resume a run. ``total=False`` lets each node return only the keys it owns.
"""

from __future__ import annotations

from typing import TypedDict

from tp_tools.models import POI, GeoLocation, RouteLeg, WeatherDaily

from tp_agents.schemas import CriticVerdict, Itinerary, PlanRequest


class PlannerState(TypedDict, total=False):
    request: PlanRequest
    geo: GeoLocation | None
    pois: list[POI]
    weather: list[WeatherDaily]
    route: list[RouteLeg]
    warnings: list[str]
    error: str | None
    itinerary: Itinerary
    # critic / corrective loop
    compose_attempts: int
    max_compose_attempts: int
    critic_verdict: CriticVerdict | None
    # per-run budget ceiling
    max_cost_usd: float
    # tenant scope, enforced as a filter at retrieval time
    tenant_id: str | None
