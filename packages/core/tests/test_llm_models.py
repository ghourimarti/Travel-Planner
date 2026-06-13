"""Routing-table contract: chain shape, OpenAI primary, pricing coverage, cost calc."""

from __future__ import annotations

import pytest
from tp_core.llm.models import MODEL_PRICING, TIER_ROUTING, cost_usd
from tp_core.llm.types import Provider, Tier


def test_every_tier_has_a_chain_with_openai_primary() -> None:
    for tier in Tier:
        chain = TIER_ROUTING[tier]
        assert chain, f"{tier} has an empty provider chain"
        assert chain[0][0] is Provider.OPENAI  # OpenAI is the available primary


def test_every_routed_model_has_pricing() -> None:
    for chain in TIER_ROUTING.values():
        for _provider, model in chain:
            assert model in MODEL_PRICING, f"missing pricing for {model}"


def test_cost_calc() -> None:
    assert cost_usd("gpt-4o-mini", 1_000_000, 0) == pytest.approx(0.15)
    assert cost_usd("gpt-4o-mini", 0, 1_000_000) == pytest.approx(0.60)
    assert cost_usd("unknown-model", 1_000_000, 1_000_000) == 0.0
