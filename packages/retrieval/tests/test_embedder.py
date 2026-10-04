"""The embedder retries transient failures instead of failing the ingest."""

from __future__ import annotations

import asyncio

from tp_retrieval.embedder import OpenAIEmbedder


def test_embedder_retries_then_succeeds(monkeypatch):
    emb = OpenAIEmbedder(api_key="test")
    calls = {"n": 0}

    class _Item:
        embedding = [0.1] * 1024

    class _Resp:
        data = [_Item()]

    async def flaky_create(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:  # a transient rate limit on the first attempt
            raise type("RateLimitError", (Exception,), {})("slow down")
        return _Resp()

    monkeypatch.setattr(emb._client.embeddings, "create", flaky_create)
    out = asyncio.run(emb.embed(["hello"]))
    assert calls["n"] == 2  # failed once, retried, succeeded
    assert len(out) == 1 and len(out[0]) == 1024


def test_query_embedding_spend_is_recorded(monkeypatch):
    """Every grounded plan embeds its query with a HOSTED model, so "local = $0.00" was
    untrue: that spend reached no ledger. It now lands in both, under its own venue."""
    import tp_core.control as control_mod
    from prometheus_client import REGISTRY

    emb = OpenAIEmbedder(api_key="test")

    class _Item:
        embedding = [0.1] * 1024

    class _Usage:
        total_tokens = 1000

    class _Resp:
        data = [_Item()]
        usage = _Usage()

    async def create(**kwargs):
        return _Resp()

    spent: list[float] = []

    async def fake_record_spend(usd: float) -> None:
        spent.append(usd)

    monkeypatch.setattr(emb._client.embeddings, "create", create)
    monkeypatch.setattr(control_mod, "record_spend", fake_record_spend)
    cost = {"provider": "openai-embeddings"}
    tokens = {"provider": "openai-embeddings", "direction": "input"}
    cost_before = REGISTRY.get_sample_value("tp_llm_cost_usd_total", cost) or 0.0
    tok_before = REGISTRY.get_sample_value("tp_llm_tokens_total", tokens) or 0.0

    asyncio.run(emb.embed(["temples in Kyoto"]))

    expected = 1000 * 0.13 / 1_000_000
    assert REGISTRY.get_sample_value("tp_llm_cost_usd_total", cost) == cost_before + expected
    assert REGISTRY.get_sample_value("tp_llm_tokens_total", tokens) == tok_before + 1000
    assert spent == [expected]  # same amount into the Redis daily ledger
