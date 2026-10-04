"""Retrieval plumbing — embed -> upsert -> city-filtered search -> typed POIs.

Uses an in-memory Qdrant + a constant fake embedder: no network, no OpenAI, no LLM.
Verifies the wiring (and the city payload filter), not semantic ranking.
"""

from __future__ import annotations

import asyncio
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from tp_retrieval.retrieve import Retriever
from tp_retrieval.vectorstore import QdrantStore, VectorRecord, city_key


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
        "city_key": city_key(city),  # normalized filter key, as real ingest writes it
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


def test_retrieve_is_case_insensitive_on_city() -> None:
    # Regression: corpus stores "Tokyo" but users type "tokyo"/"TOKYO". A case-sensitive
    # filter returned zero hits and silently fell through to (bad) live POIs.
    store = _store_with([_rec("Tokyo", "Senso-ji"), _rec("Kyoto", "Kinkaku-ji")])
    retriever = Retriever(_FakeEmbedder(), store)
    for query in ("tokyo", "TOKYO", "  Tokyo  "):
        names = [p.name for p in asyncio.run(retriever.retrieve(query, ["temples"]))]
        assert "Senso-ji" in names, f"case-insensitive match failed for {query!r}"
        assert "Kinkaku-ji" not in names


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


# --- embedder provenance check ------------------------------------------------------


class _NamedEmbedder(_FakeEmbedder):
    def __init__(self, model: str) -> None:
        self.model = model


def _stamped_store(embedder_model: str) -> QdrantStore:
    store = _store_with([_rec("Kyoto", "Kinkaku-ji")])
    asyncio.run(store.write_meta(embedder_model=embedder_model, dim=4))
    return store


def _mismatches() -> float:
    from prometheus_client import REGISTRY

    return REGISTRY.get_sample_value("tp_errors_total", {"type": "embedder_mismatch"}) or 0.0


def test_embedder_mismatch_is_detected_from_a_sync_caller() -> None:
    from tp_retrieval.retrieve import _warn_on_embedder_mismatch

    store = _stamped_store("text-embedding-3-large")
    before = _mismatches()
    _warn_on_embedder_mismatch(_NamedEmbedder("voyage-3"), store)
    assert _mismatches() == before + 1


def test_embedder_mismatch_is_detected_inside_a_running_loop() -> None:
    """The WORKER path: the retriever is built inside the first run's event loop.

    This is the case that silently never ran. asyncio.run() inside a running loop always
    raises; a bare except swallowed it, so the counter could not move even on a real
    mismatch. The only trace was a 'coroutine was never awaited' warning in the log.
    """
    from tp_retrieval.retrieve import _PENDING_CHECKS, _warn_on_embedder_mismatch

    store = _stamped_store("text-embedding-3-large")
    before = _mismatches()

    async def worker_first_run() -> None:
        _warn_on_embedder_mismatch(_NamedEmbedder("voyage-3"), store)
        await asyncio.gather(*list(_PENDING_CHECKS))

    asyncio.run(worker_first_run())
    assert _mismatches() == before + 1


def test_matching_embedder_records_nothing() -> None:
    from tp_retrieval.retrieve import _warn_on_embedder_mismatch

    store = _stamped_store("text-embedding-3-large")
    before = _mismatches()
    _warn_on_embedder_mismatch(_NamedEmbedder("text-embedding-3-large"), store)
    assert _mismatches() == before
