"""Vector store behind an interface (Decision 2) so the engine is swappable.

The Qdrant client runs in embedded/local mode by default (a path on disk, or
``:memory:`` for tests) — no Docker needed in dev. A real Qdrant server is wired
via ``QDRANT_URL`` in Phase 6. Sync client calls are offloaded to a thread so the
async agent/eval paths never block the event loop.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

from pydantic import BaseModel
from qdrant_client import QdrantClient, models
from tp_core.settings import Settings, get_settings

COLLECTION = "pois"


def city_key(city: str) -> str:
    """Canonical, case-insensitive key for city filtering.

    The corpus stores display names like ``"Tokyo"`` but callers pass whatever the
    user typed (``"tokyo"``, ``"TOKYO"``). Filtering on the raw ``city`` string is
    case-sensitive in Qdrant, so a casing mismatch silently returns zero hits and the
    planner falls through to live POIs. We index and filter on this normalized key so
    grounding survives any casing/whitespace, while the human-readable ``city`` payload
    is preserved for display.
    """
    return city.strip().casefold()


class VectorRecord(BaseModel):
    id: str
    vector: list[float]
    payload: dict[str, Any]


class ScoredPayload(BaseModel):
    score: float
    payload: dict[str, Any]


class VectorStore(Protocol):
    async def ensure_collection(self) -> None: ...
    async def upsert(self, records: list[VectorRecord]) -> None: ...
    async def search(
        self, vector: list[float], *, city: str, limit: int, tenant_id: str | None = None
    ) -> list[ScoredPayload]: ...


class QdrantStore:
    def __init__(self, client: QdrantClient, *, dim: int, collection: str = COLLECTION) -> None:
        self._client = client
        self._dim = dim
        self._collection = collection

    @classmethod
    def from_settings(cls, *, dim: int, settings: Settings | None = None) -> QdrantStore:
        cfg = settings or get_settings()
        client = (
            QdrantClient(url=cfg.qdrant_url)
            if cfg.qdrant_url
            else QdrantClient(path=cfg.qdrant_path)
        )
        return cls(client, dim=dim)

    async def ensure_collection(self) -> None:
        def _ensure() -> None:
            if not self._client.collection_exists(self._collection):
                self._client.create_collection(
                    self._collection,
                    vectors_config=models.VectorParams(
                        size=self._dim, distance=models.Distance.COSINE
                    ),
                )

        await asyncio.to_thread(_ensure)

    async def upsert(self, records: list[VectorRecord]) -> None:
        points = [
            models.PointStruct(id=r.id, vector=r.vector, payload=r.payload) for r in records
        ]
        await asyncio.to_thread(self._client.upsert, self._collection, points)

    async def search(
        self, vector: list[float], *, city: str, limit: int, tenant_id: str | None = None
    ) -> list[ScoredPayload]:
        must: list[models.FieldCondition] = [
            # Filter on the normalized key so "tokyo"/"Tokyo"/"TOKYO" all match the
            # corpus (payloads carry both `city` for display and `city_key` for filtering).
            models.FieldCondition(key="city_key", match=models.MatchValue(value=city_key(city)))
        ]
        if tenant_id is not None:  # ACL: own private docs + the shared public corpus (S12c)
            must.append(
                models.FieldCondition(
                    key="tenant_id", match=models.MatchAny(any=[tenant_id, "public"])
                )
            )
        flt = models.Filter(must=must)

        def _search() -> list[models.ScoredPoint]:
            resp = self._client.query_points(
                collection_name=self._collection,
                query=vector,
                query_filter=flt,
                limit=limit,
            )
            return resp.points

        hits = await asyncio.to_thread(_search)
        return [ScoredPayload(score=h.score, payload=dict(h.payload or {})) for h in hits]

    def close(self) -> None:
        """Flush + close the (local) client so data persists and shutdown is clean."""
        self._client.close()
