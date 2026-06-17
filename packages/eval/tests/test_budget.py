"""S10b: the eval under_budget gate keys off the single budget constant."""

from __future__ import annotations

from tp_agents.schemas import Itinerary
from tp_eval.metrics import score_trajectory


def test_under_budget_gate():
    cheap = score_trajectory(
        "c", 1, Itinerary(city="X", summary_markdown="y", cost_usd=0.01), provided_names=[]
    )
    assert cheap.under_budget is True
    pricey = score_trajectory(
        "c", 1, Itinerary(city="X", summary_markdown="y", cost_usd=0.99), provided_names=[]
    )
    assert pricey.under_budget is False
