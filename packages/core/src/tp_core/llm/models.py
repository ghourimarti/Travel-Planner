"""Tier -> provider/model routing + pricing (Decision 4, amended S2: OpenAI primary).

The chain order is the fallback order: OpenAI (available primary) -> Anthropic ->
Groq. The gateway skips any provider whose API key is absent, so the chain is
self-pruning. Non-OpenAI/Anthropic model IDs and all non-Anthropic prices are
CONFIG — verify against each provider's current catalog/pricing page. Anthropic
IDs + prices are authoritative (claude-api reference, 2026-06).
"""

from __future__ import annotations

from tp_core.llm.types import Provider, Tier

TIER_ROUTING: dict[Tier, list[tuple[Provider, str]]] = {
    Tier.CHEAP: [
        (Provider.OPENAI, "gpt-4o-mini"),
        (Provider.GROQ, "llama-3.1-8b-instant"),
        (Provider.ANTHROPIC, "claude-haiku-4-5"),
    ],
    Tier.MID: [
        (Provider.OPENAI, "gpt-4o"),
        (Provider.GROQ, "llama-3.3-70b-versatile"),
        (Provider.ANTHROPIC, "claude-sonnet-4-6"),
    ],
    Tier.FRONTIER: [
        # TODO(config): set your OpenAI frontier model (e.g. a reasoning model).
        (Provider.OPENAI, "gpt-4o"),
        (Provider.ANTHROPIC, "claude-opus-4-8"),
        (Provider.GROQ, "llama-3.3-70b-versatile"),
    ],
}

# USD per 1M tokens: (input, output).
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI — VERIFY at https://openai.com/api/pricing
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    # Anthropic — authoritative (claude-api)
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-8": (5.00, 25.00),
    # Groq — VERIFY at https://groq.com/pricing
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.3-70b-versatile": (0.59, 0.79),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute call cost from the pricing table (0.0 for unknown models)."""
    price_in, price_out = MODEL_PRICING.get(model, (0.0, 0.0))
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000
