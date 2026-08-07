"""Ingestion pipeline: corpus -> embed -> upsert to Qdrant.

    uv run python -m tp_retrieval.ingest        # ingest the seed corpus

Needs OPENAI_API_KEY (or VOYAGE_API_KEY) for embeddings.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from tp_retrieval.corpus import load_corpus
from tp_retrieval.embedder import Embedder, get_embedder
from tp_retrieval.vectorstore import QdrantStore, VectorRecord, VectorStore, city_key


async def ingest(*, embedder: Embedder, store: VectorStore, path: Path | None = None) -> int:
    docs = load_corpus(path)
    await store.ensure_collection()
    vectors = await embedder.embed([d.embed_text() for d in docs])
    records = [
        VectorRecord(
            id=str(uuid5(NAMESPACE_URL, f"{d.city}:{d.name}")),
            vector=vec,
            # Seed corpus is shared: "public" matches every tenant's ACL filter.
            # `city_key` is the normalized filter key (see vectorstore.city_key) so
            # retrieval matches regardless of how the user cased the city name.
            payload={"tenant_id": "public", "city_key": city_key(d.city), **d.model_dump()},
        )
        for d, vec in zip(docs, vectors, strict=True)
    ]
    await store.upsert(records)
    return len(records)


def main() -> None:
    embedder = get_embedder()
    store = QdrantStore.from_settings(dim=embedder.dim)
    try:
        count = asyncio.run(ingest(embedder=embedder, store=store))
        print(f"Ingested {count} POIs into Qdrant.")
    finally:
        store.close()  # flush local Qdrant to disk so the next process sees the collection


if __name__ == "__main__":
    main()
