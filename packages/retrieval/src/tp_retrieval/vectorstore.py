"""Vector store behind an interface so the engine stays swappable.

The Qdrant client runs in embedded/local mode by default (a path on disk, or
``:memory:`` for tests) — no Docker needed in dev; a real server is wired via
``QDRANT_URL``. Sync client calls are offloaded to a thread so the async agent/eval
paths never block the event loop.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

from pydantic import BaseModel
from qdrant_client import QdrantClient, models
from tp_core.settings import Settings, get_settings

COLLECTION = "pois"

#: Fixed id for a sentinel point carrying index provenance. A point rather than an
#: external file so the fact travels WITH the collection: restore the volume and the
#: provenance comes back with it, which a sidecar file would not.
#: Excluded from search by its own payload marker (`_meta`), and harmless if read as
#: a normal point since it carries no `name` field and retrieval skips those.
META_POINT_ID = "00000000-0000-0000-0000-0000000000ff"


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

    async def write_meta(self, *, embedder_model: str, dim: int) -> None:
        """Stamp the collection with the embedder that built it."""

        def _write() -> None:
            self._client.upsert(
                self._collection,
                [models.PointStruct(
                    id=META_POINT_ID,
                    vector=[0.0] * self._dim,
                    payload={"_meta": True, "embedder_model": embedder_model, "dim": dim},
                )],
            )

        await asyncio.to_thread(_write)

    async def read_meta(self) -> dict[str, Any] | None:
        """The embedder provenance stamped at ingest, or None if absent/unreadable.

        None is not an error: a collection built before this existed simply has no
        stamp, and refusing to serve on that basis would break every existing index.
        """

        def _read() -> dict[str, Any] | None:
            try:
                pts = self._client.retrieve(self._collection, ids=[META_POINT_ID])
            except Exception:
                return None
            return dict(pts[0].payload) if pts and pts[0].payload else None

        return await asyncio.to_thread(_read)

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
        # Tenant ACL enforced HERE, in the query — not after generation, so a caller can
        # never be shown another tenant's documents. Production ALWAYS passes a tenant_id (auth is
        # fail-closed outside local), so real traffic is always scoped to the caller's own
        # private docs + the shared "public" corpus. tenant_id is None only on the eval /
        # direct-call path, which sees the public-only seed corpus (no private tenants exist
        # there), so the city filter alone is safe. If keyless MULTI-tenant use is ever added,
        # add a `tenant_id == "public"` fallback on this branch.
        if tenant_id is not None:
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
