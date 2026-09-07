"""Retriever: embed query -> dense search (city-filtered) -> rerank -> typed POIs.

``get_retriever`` builds a process-wide singleton from settings (one Qdrant client,
so the local file isn't opened twice). Tests construct ``Retriever`` directly with
fakes.
"""

from __future__ import annotations

import asyncio
import atexit
from typing import Protocol

from tp_core.llm import LLMGateway
from tp_core.logging import get_logger
from tp_core.metrics import record_error
from tp_core.settings import get_settings
from tp_tools.models import POI

from tp_retrieval.embedder import Embedder, get_embedder
from tp_retrieval.rerank import LLMReranker
from tp_retrieval.vectorstore import QdrantStore, VectorStore


class _Reranker(Protocol):
    async def rerank(
        self, city: str, interests: list[str], pois: list[POI], *, top_n: int
    ) -> list[POI]: ...


class Retriever:
    def __init__(
        self, embedder: Embedder, store: VectorStore, reranker: _Reranker | None = None
    ) -> None:
        self._embedder = embedder
        self._store = store
        self._reranker = reranker

    async def retrieve(
        self,
        city: str,
        interests: list[str],
        *,
        k: int | None = None,
        top_n: int | None = None,
        tenant_id: str | None = None,
    ) -> list[POI]:
        # None means "ask config", not "use a magic number". An EXPLICIT argument still
        # wins, so callers that already tune depth per call-point are unaffected — the
        # settings only supply the default that used to be hardcoded here as 20/8.
        cfg = get_settings()
        k = cfg.retrieval_top_k if k is None else k
        top_n = cfg.rerank_top_k if top_n is None else top_n
        query = f"{', '.join(interests)} in {city}"
        vector = (await self._embedder.embed([query]))[0]
        hits = await self._store.search(vector, city=city, limit=k, tenant_id=tenant_id)
        pois = [
            POI(
                name=str(h.payload["name"]),
                category=str(h.payload["category"]),
                latitude=float(h.payload["latitude"]),
                longitude=float(h.payload["longitude"]),
            )
            for h in hits
            if "name" in h.payload
        ]
        if self._reranker is not None and pois:
            return await self._reranker.rerank(city, interests, pois, top_n=top_n)
        return pois[:top_n]


_log = get_logger("tp_retrieval.retrieve")

_RETRIEVER: Retriever | None = None


def get_retriever(gateway: LLMGateway | None = None) -> Retriever:
    """Process-wide retriever from settings (embedder + Qdrant + LLM reranker)."""
    global _RETRIEVER
    if _RETRIEVER is None:
        embedder = get_embedder()
        store = QdrantStore.from_settings(dim=embedder.dim)
        reranker = LLMReranker(gateway or LLMGateway.from_settings())
        _RETRIEVER = Retriever(embedder, store, reranker)
        _warn_on_embedder_mismatch(embedder, store)
        atexit.register(store.close)  # graceful close on process exit (no shutdown noise)
    return _RETRIEVER


def _warn_on_embedder_mismatch(embedder: Embedder, store: QdrantStore) -> None:
    """Compare the query embedder against the one that built the index.

    LOUD, NEVER FATAL. This runs on the request path; raising here would take a
    working app down to report a config smell, and a mismatched embedder still returns
    plausible results — it is a quality failure, not a correctness one. So it logs a
    warning and increments `tp_errors{type="embedder_mismatch"}`, which the dashboard's
    "Errors by type" panel already charts.

    A missing stamp is NOT a mismatch: indexes built before provenance existed have
    none, and treating absence as failure would cry wolf on every one of them.
    """
    try:
        meta = asyncio.run(store.read_meta())
    except Exception:  # never let a diagnostic break startup
        return
    if not meta:
        return
    indexed = str(meta.get("embedder_model", ""))
    current = getattr(embedder, "model", "")
    if indexed and current and indexed != current:
        record_error("embedder_mismatch")
        _log.warning(
            "embedder_mismatch",
            indexed_with=indexed,
            querying_with=current,
            impact=(
                "query vectors live in a different space from the index; retrieval "
                "still returns ranked results, they are just quietly worse. Re-ingest "
                "with `make seed`, or switch back to the indexed model."
            ),
        )
