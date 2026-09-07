"""Tier -> provider/model routing + pricing.

The chain order is the fallback order: OpenAI (primary) -> Anthropic ->
Groq. The gateway skips any provider whose API key is absent, so the chain is
self-pruning. Non-OpenAI/Anthropic model IDs and all non-Anthropic prices are
CONFIG — verify against each provider's current catalog/pricing page. Anthropic
IDs + prices are authoritative (Anthropic API docs, 2026-06).
"""

from __future__ import annotations

from tp_core.llm.types import Provider, Tier

TIER_ROUTING: dict[Tier, list[tuple[Provider, str]]] = {
    Tier.CHEAP: [
        (Provider.OPENAI, "gpt-4o-mini"),
        (Provider.GROQ, "qwen/qwen3.8-27b"),
        (Provider.ANTHROPIC, "claude-haiku-4-5"),
    ],
    Tier.MID: [
        (Provider.OPENAI, "gpt-4o"),
        (Provider.GROQ, "qwen/qwen3.8-27b"),
        (Provider.ANTHROPIC, "claude-sonnet-4-6"),
    ],
    Tier.FRONTIER: [
        # With OpenAI primary, gpt-4o IS OpenAI's flagship general model, so the
        # FRONTIER rung equals MID for the primary provider — an intentional collapse, not a
        # gap. True frontier ESCALATION happens on the next rung: with an ANTHROPIC_API_KEY
        # set, the critic/planner run on claude-opus-4-8. To escalate on OpenAI instead, swap
        # this to a reasoning model (e.g. an o-series model) and add its price to MODEL_PRICING.
        (Provider.OPENAI, "gpt-4o"),
        (Provider.ANTHROPIC, "claude-opus-4-8"),
        (Provider.GROQ, "qwen/qwen3.8-27b"),
    ],
}

# USD per 1M tokens: (input, output). Values as of 2026-07 — provider prices drift, so
# re-verify at each provider's pricing page. NOTE: an unknown model returns (0.0, 0.0) in
# cost_usd() below, which UNDER-reports spend — keep every routed model priced here.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI — verify at https://openai.com/api/pricing
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    # Anthropic — authoritative (Anthropic API docs)
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-8": (5.00, 25.00),
    # Groq — verify at https://groq.com/pricing
    # 2026-09-07: llama-3.1-8b-instant and llama-3.3-70b-versatile were RETIRED by Groq
    # and returned 404 on EVERY call, so the whole Groq rung was a no-op and traffic fell
    # silently through to the paid OpenAI rung. Replaced with the one currently-served
    # Groq model that behaves like an instruct model: the gpt-oss-* pair return EMPTY
    # message.content (reasoning models) and qwen3.6 leaks <think> into the content -
    # both break structured output.
    #
    # PRICE VERIFIED 2026-09-07 against console.groq.com/docs/models.md and the model
    # page: "$0.80 input $4.00 output" per 1M tokens. It replaces an ESTIMATE of
    # (0.29, 0.59) that was out by 2.8x on input and 6.8x on OUTPUT - and output is
    # where itinerary spend actually lands. It erred in the dangerous direction:
    # cost_usd() feeds the per-itinerary cap AND the eval budget gate, so both were
    # admitting several times more real spend than they reported. An estimate in a cost
    # table is not a placeholder; it is a wrong answer wearing a right answer's clothes.
    #
    # The cheap alternative is NOT usable at any price: openai/gpt-oss-20b is
    # $0.075/$0.30 - 10x cheaper - but returns EMPTY message.content.
    "qwen/qwen3.8-27b": (0.80, 4.00),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute call cost from the pricing table (0.0 for unknown models)."""
    price_in, price_out = MODEL_PRICING.get(model, (0.0, 0.0))
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000
