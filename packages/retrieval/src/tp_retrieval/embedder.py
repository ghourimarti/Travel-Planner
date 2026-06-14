"""Embedders behind one interface. Dimension is PINNED at 1024 (Decision 5).

Voyage is used iff ``VOYAGE_API_KEY`` is set, else OpenAI ``text-embedding-3-large``
with ``dimensions=1024`` — both emit 1024-d vectors, so swapping providers (or to a
self-hosted bge-m3 later) is a re-index, not a re-embed.
"""

from __future__ import annotations

from typing import Protocol

from openai import AsyncOpenAI
from tp_core.settings import Settings, get_settings

EMBED_DIM = 1024


class Embedder(Protocol):
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    """OpenAI text-embedding-3-large, reduced to 1024 dims via the `dimensions` param."""

    model = "text-embedding-3-large"

    def __init__(self, api_key: str, *, dim: int = EMBED_DIM) -> None:
        self.dim = dim
        self._client = AsyncOpenAI(api_key=api_key)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        resp = await self._client.embeddings.create(
            model=self.model, input=texts, dimensions=self.dim
        )
        return [item.embedding for item in resp.data]


class VoyageEmbedder:
    """Voyage voyage-3 (1024-d). Lazy-imports voyageai so it's inert without a key."""

    model = "voyage-3"

    def __init__(self, api_key: str, *, dim: int = EMBED_DIM) -> None:
        import voyageai

        self.dim = dim
        self._client = voyageai.AsyncClient(api_key=api_key)  # type: ignore[attr-defined]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        result = await self._client.embed(texts, model=self.model, input_type="document")
        return [list(v) for v in result.embeddings]


def get_embedder(settings: Settings | None = None) -> Embedder:
    """Voyage iff a key is configured, else OpenAI — both at the pinned 1024-d."""
    cfg = settings or get_settings()
    if cfg.voyage_api_key:
        return VoyageEmbedder(cfg.voyage_api_key)
    return OpenAIEmbedder(cfg.openai_api_key)
