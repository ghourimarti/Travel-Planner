"""Deterministic trajectory metrics — free, fast, no LLM. This is the CI-gateable layer."""

from __future__ import annotations

from pydantic import BaseModel
from tp_agents.schemas import Itinerary

_BUDGET_USD = 0.30  # the Phase-1 per-itinerary ceiling


class ScoreCard(BaseModel):
    case_id: str
    success: bool  # produced an itinerary at all
    grounded: bool  # the planner's own grounded flag
    pois_provided: int
    pois_used: int
    poi_coverage: float  # fraction of provided POIs actually named in the summary
    cost_usd: float
    under_budget: bool
    honest_on_degrade: bool  # if no POIs were provided, a warning must be present
    schema_valid: bool


def _coverage(provided_names: list[str], summary: str) -> float:
    if not provided_names:
        return 1.0  # nothing to cover
    hay = summary.lower()
    hit = sum(1 for n in provided_names if n.lower() in hay)
    return round(hit / len(provided_names), 3)


def score_trajectory(
    case_id: str, provided_pois: int, itinerary: Itinerary, *, provided_names: list[str]
) -> ScoreCard:
    degraded = provided_pois == 0
    return ScoreCard(
        case_id=case_id,
        success=bool(itinerary.summary_markdown.strip()),
        grounded=itinerary.grounded,
        pois_provided=provided_pois,
        pois_used=len(itinerary.pois_used),
        poi_coverage=_coverage(provided_names, itinerary.summary_markdown),
        cost_usd=itinerary.cost_usd,
        under_budget=itinerary.cost_usd <= _BUDGET_USD,
        honest_on_degrade=(not degraded) or bool(itinerary.warnings),
        schema_valid=isinstance(itinerary, Itinerary),
    )
