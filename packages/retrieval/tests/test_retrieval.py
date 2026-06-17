"""S6: retrieval plumbing — embed -> upsert -> city-filtered search -> typed POIs.

Uses an in-memory Qdrant + a constant fake embedder: no network, no OpenAI, no LLM.
Verifies the wiring (and the city payload filter), not semantic ranking.
"""

from __future__ import annotations

import asyncio
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from tp_retrieval.retrieve import Retriever
from tp_retrieval.vectorstore import QdrantStore, VectorRecord


class _FakeEmbedder:
    dim = 4

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


def _rec(city: str, name: str, tenant_id: str | None = None) -> VectorRecord:
    payload: dict = {
        "name": name,
        "category": "temples",
        "latitude": 35.0,
        "longitude": 135.0,
        "city": city,
    }
    if tenant_id is not None:
        payload["tenant_id"] = tenant_id
    return VectorRecord(
        id=str(uuid5(NAMESPACE_URL, f"{city}:{name}:{tenant_id}")),
        vector=[1.0, 0.0, 0.0, 0.0],
        payload=payload,
    )


def _store_with(records: list[VectorRecord]) -> QdrantStore:
    store = QdrantStore(QdrantClient(location=":memory:"), dim=4)
    asyncio.run(store.ensure_collection())
    asyncio.run(store.upsert(records))
    return store


def test_retrieve_filters_by_city() -> None:
    store = _store_with([_rec("Kyoto", "Kinkaku-ji"), _rec("Tokyo", "Senso-ji")])
    retriever = Retriever(_FakeEmbedder(), store)
    names = [p.name for p in asyncio.run(retriever.retrieve("Kyoto", ["temples"]))]
    assert "Kinkaku-ji" in names
    assert "Senso-ji" not in names  # the city payload filter excludes Tokyo


def test_retrieve_empty_city_returns_nothing() -> None:
    store = _store_with([_rec("Kyoto", "Kinkaku-ji")])
    retriever = Retriever(_FakeEmbedder(), store)
    assert asyncio.run(retriever.retrieve("Atlantis", ["temples"])) == []


def test_acl_scopes_retrieval_by_tenant() -> None:
    store = _store_with(
        [
            _rec("Kyoto", "Public-Shrine", tenant_id="public"),
            _rec("Kyoto", "Acme-Private", tenant_id="acme"),
            _rec("Kyoto", "Globex-Private", tenant_id="globex"),
        ]
    )
    retriever = Retriever(_FakeEmbedder(), store)

    acme = [p.name for p in asyncio.run(retriever.retrieve("Kyoto", ["temples"], tenant_id="acme"))]
    assert "Acme-Private" in acme  # own private docs
    assert "Public-Shrine" in acme  # plus the shared public corpus
    assert "Globex-Private" not in acme  # never another tenant's private docs


def test_no_tenant_keeps_city_only_behavior() -> None:
    # tenant_id=None (eval/legacy) → city filter only, no ACL restriction.
    store = _store_with([_rec("Kyoto", "Acme-Private", tenant_id="acme")])
    retriever = Retriever(_FakeEmbedder(), store)
    names = [p.name for p in asyncio.run(retriever.retrieve("Kyoto", ["temples"]))]
    assert "Acme-Private" in names
