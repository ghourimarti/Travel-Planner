"""Retriever: embed query -> dense search (city-filtered) -> rerank -> typed POIs.

``get_retriever`` builds a process-wide singleton from settings (one Qdrant client,
so the local file isn't opened twice). Tests construct ``Retriever`` directly with
fakes.
"""

from __future__ import annotations

import atexit
from typing import Protocol

from tp_core.llm import LLMGateway
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
        self, city: str, interests: list[str], *, k: int = 20, top_n: int = 8
    ) -> list[POI]:
        query = f"{', '.join(interests)} in {city}"
        vector = (await self._embedder.embed([query]))[0]
        hits = await self._store.search(vector, city=city, limit=k)
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


_RETRIEVER: Retriever | None = None


def get_retriever(gateway: LLMGateway | None = None) -> Retriever:
    """Process-wide retriever from settings (embedder + Qdrant + LLM reranker)."""
    global _RETRIEVER
    if _RETRIEVER is None:
        embedder = get_embedder()
        store = QdrantStore.from_settings(dim=embedder.dim)
        reranker = LLMReranker(gateway or LLMGateway.from_settings())
        _RETRIEVER = Retriever(embedder, store, reranker)
        atexit.register(store.close)  # graceful close on process exit (no shutdown noise)
    return _RETRIEVER
