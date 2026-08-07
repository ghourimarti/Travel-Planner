"""The cost cap halts the critic's revise-loop once the run hits its budget."""

from __future__ import annotations

from tp_agents.graph import _should_revise
from tp_agents.schemas import CriticVerdict, Itinerary


def _state(cost: float, budget: float = 0.30):
    # The critic WANTS a revision and an attempt remains — only the cost cap can stop it.
    return {
        "critic_verdict": CriticVerdict(ok=False, issues=["fix it"]),
        "compose_attempts": 1,
        "max_compose_attempts": 2,
        "itinerary": Itinerary(city="X", summary_markdown="y", cost_usd=cost),
        "max_cost_usd": budget,
    }


def test_cost_cap_stops_revision():
    assert _should_revise(_state(cost=0.50)) == "end"  # over budget -> no re-compose


def test_revises_when_under_budget():
    assert _should_revise(_state(cost=0.001)) == "revise"  # under budget -> revise as normal
