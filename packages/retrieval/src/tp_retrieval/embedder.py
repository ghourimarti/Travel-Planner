"""Embedders behind one interface. Dimension is PINNED at 1024.

Voyage is used iff ``VOYAGE_API_KEY`` is set, else OpenAI ``text-embedding-3-large``
with ``dimensions=1024`` — both emit 1024-d vectors, so swapping providers (or to a
self-hosted bge-m3 later) is a re-index, not a re-embed.
"""

from __future__ import annotations

from typing import Protocol

from openai import AsyncOpenAI
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential
from tp_core.settings import Settings, get_settings

EMBED_DIM = 1024


def _is_transient(exc: BaseException) -> bool:
    """Retry rate-limit / timeout / connection / 5xx, matched by exception class name.

    Class-name matching keeps this provider-agnostic: OpenAI and Voyage raise their own
    error types, but both name them consistently enough to classify without importing either.
    """
    name = type(exc).__name__
    keys = (
        "RateLimit",
        "Timeout",
        "Connection",
        "ServiceUnavailable",
        "InternalServer",
        "APIError",
    )
    return any(k in name for k in keys)


_retry = retry(
    retry=retry_if_exception(_is_transient),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=0.5, max=10),
    reraise=True,
)


class Embedder(Protocol):
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    """OpenAI text-embedding-3-large, reduced to 1024 dims via the `dimensions` param."""

    model = "text-embedding-3-large"

    def __init__(self, api_key: str, *, dim: int = EMBED_DIM) -> None:
        self.dim = dim
        self._client = AsyncOpenAI(api_key=api_key)

    @_retry
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

    @_retry
    async def embed(self, texts: list[str]) -> list[list[float]]:
        result = await self._client.embed(texts, model=self.model, input_type="document")
        return [list(v) for v in result.embeddings]


def get_embedder(settings: Settings | None = None) -> Embedder:
    """Voyage iff a key is configured, else OpenAI — both at the pinned 1024-d."""
    cfg = settings or get_settings()
    if cfg.voyage_api_key:
        return VoyageEmbedder(cfg.voyage_api_key)
    return OpenAIEmbedder(cfg.openai_api_key)
