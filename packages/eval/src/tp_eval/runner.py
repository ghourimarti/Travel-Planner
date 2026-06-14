"""Run the golden set through the REAL compose node; aggregate a report.

By default each case uses its FIXED fixture POIs (reproducible — the S5 baseline).
With a ``retriever`` (``--retrieve``) it instead RETRIEVES POIs from the corpus per
case, measuring the real retrieval grounding (the S6 lift over the S5 baseline).
Either way we reuse the production ``compose_node`` seam.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel
from tp_agents.nodes import compose_node
from tp_agents.schemas import Itinerary, PlanRequest
from tp_agents.state import PlannerState
from tp_core.llm import LLMGateway
from tp_tools.models import POI, GeoLocation

from tp_eval.golden import GoldenCase
from tp_eval.judge import JudgeResult
from tp_eval.metrics import ScoreCard, score_trajectory


class Judge(Protocol):
    async def judge(
        self, request: PlanRequest, allowed_names: list[str], itinerary: Itinerary
    ) -> JudgeResult: ...


class PoiRetriever(Protocol):
    async def retrieve(self, city: str, interests: list[str]) -> list[POI]: ...


class CaseResult(BaseModel):
    scorecard: ScoreCard
    judge: JudgeResult | None = None


class EvalReport(BaseModel):
    n_cases: int
    success_rate: float
    grounded_rate: float
    mean_poi_coverage: float
    mean_cost_usd: float
    under_budget_rate: float
    honest_on_degrade_rate: float
    faithfulness_rate: float | None = None
    mean_relevance: float | None = None
    results: list[CaseResult]


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


async def run_eval(
    cases: list[GoldenCase],
    *,
    gateway: LLMGateway,
    judge: Judge | None = None,
    retriever: PoiRetriever | None = None,
) -> EvalReport:
    results: list[CaseResult] = []
    for case in cases:
        grounding = (
            await retriever.retrieve(case.request.city, case.request.interests)
            if retriever is not None
            else list(case.pois)
        )
        state: PlannerState = {
            "request": case.request,
            "geo": GeoLocation(name=case.request.city, latitude=0.0, longitude=0.0),
            "pois": grounding,
            "weather": list(case.weather),
            "warnings": [],
        }
        out = await compose_node(state, gateway)
        itinerary: Itinerary = out["itinerary"]
        names = [p.name for p in grounding]
        scorecard = score_trajectory(case.id, len(grounding), itinerary, provided_names=names)
        jr = await judge.judge(case.request, names, itinerary) if judge is not None else None
        results.append(CaseResult(scorecard=scorecard, judge=jr))

    cards = [r.scorecard for r in results]
    judged = [r.judge for r in results if r.judge is not None]
    return EvalReport(
        n_cases=len(results),
        success_rate=_mean([float(c.success) for c in cards]),
        grounded_rate=_mean([float(c.grounded) for c in cards]),
        mean_poi_coverage=_mean([c.poi_coverage for c in cards]),
        mean_cost_usd=_mean([c.cost_usd for c in cards]),
        under_budget_rate=_mean([float(c.under_budget) for c in cards]),
        honest_on_degrade_rate=_mean([float(c.honest_on_degrade) for c in cards]),
        faithfulness_rate=_mean([j.faithfulness_score for j in judged]) if judged else None,
        mean_relevance=_mean([j.relevance_score for j in judged]) if judged else None,
        results=results,
    )
