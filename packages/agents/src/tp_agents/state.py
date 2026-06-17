"""LangGraph state for the single-agent planner.

Kept to serializable values (Pydantic models + builtins) so the Postgres
checkpointer added in S9 can persist and resume a run. ``total=False`` lets each
node return only the keys it owns.
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
    # multi-agent / corrective loop (S7)
    compose_attempts: int
    max_compose_attempts: int
    critic_verdict: CriticVerdict | None
    # cost cap (S10b)
    max_cost_usd: float
    # tenant scope for ACL-at-retrieval (S12c)
    tenant_id: str | None
