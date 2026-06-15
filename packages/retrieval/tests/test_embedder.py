"""S10a: the embedder retries transient failures (the S6 deferral)."""

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
