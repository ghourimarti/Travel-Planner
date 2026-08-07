"""Deterministic metrics + runner aggregate, with the LLM mocked (free, offline)."""

from __future__ import annotations

import asyncio

from tp_agents.schemas import Itinerary, PlanRequest
from tp_core.llm import LLMResponse, Message, Provider, Tier, Usage
from tp_eval.golden import GoldenCase
from tp_eval.metrics import score_trajectory
from tp_eval.runner import run_eval
from tp_tools.models import POI


def test_score_trajectory_grounded() -> None:
    itin = Itinerary(
        city="Tokyo",
        summary_markdown="Morning: Senso-ji. Afternoon: Meiji Shrine.",
        pois_used=[
            POI(name="Senso-ji", category="temples", latitude=0.0, longitude=0.0),
            POI(name="Meiji Shrine", category="temples", latitude=0.0, longitude=0.0),
        ],
        grounded=True,
        cost_usd=0.002,
    )
    sc = score_trajectory("t", 2, itin, provided_names=["Senso-ji", "Meiji Shrine"])
    assert sc.success and sc.grounded
    assert sc.poi_coverage == 1.0
    assert sc.under_budget


def test_degraded_case_must_warn() -> None:
    warned = Itinerary(
        city="X",
        summary_markdown="No POIs available.",
        grounded=False,
        warnings=["No POIs found."],
    )
    assert score_trajectory("x", 0, warned, provided_names=[]).honest_on_degrade is True

    silent = Itinerary(city="X", summary_markdown="text", grounded=False, warnings=[])
    assert score_trajectory("x", 0, silent, provided_names=[]).honest_on_degrade is False


class _FakeGateway:
    async def complete(
        self, messages: list[Message], tier: Tier, *, max_tokens: int = 1024
    ) -> LLMResponse:
        return LLMResponse(
            text="Visit Senso-ji in the morning.",
            provider=Provider.OPENAI,
            model="gpt-4o",
            tier=tier,
            usage=Usage(input_tokens=10, output_tokens=5, cost_usd=0.001),
        )


def test_run_eval_without_judge_aggregates() -> None:
    cases = [
        GoldenCase(
            id="c1",
            request=PlanRequest(city="Tokyo", interests=["temples"]),
            pois=[POI(name="Senso-ji", category="temples", latitude=0.0, longitude=0.0)],
            weather=[],
        )
    ]
    report = asyncio.run(run_eval(cases, gateway=_FakeGateway(), judge=None))  # type: ignore[arg-type]
    assert report.n_cases == 1
    assert report.success_rate == 1.0
    assert report.grounded_rate == 1.0
    assert report.faithfulness_rate is None
