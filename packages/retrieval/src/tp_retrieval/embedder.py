"""Embedders behind one interface. Dimension is PINNED at 1024.

Voyage is used iff ``VOYAGE_API_KEY`` is set, else OpenAI ``text-embedding-3-large``
with ``dimensions=1024`` — both emit 1024-d vectors, so swapping providers (or to a
self-hosted bge-m3 later) is a re-index, not a re-embed.
"""

from __future__ import annotations

from typing import Protocol

from openai import AsyncOpenAI
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential
from tp_core.metrics import record_venue_usage
from tp_core.settings import Settings, get_settings

EMBED_DIM = 1024

#: USD per 1M input tokens (OpenAI / Voyage list prices).
_PRICE_PER_MTOK = {"text-embedding-3-large": 0.13, "voyage-3": 0.06}

#: The venue label embedding spend is recorded under - deliberately NOT a serving venue.
EMBEDDING_VENUE = {"text-embedding-3-large": "openai-embeddings", "voyage-3": "voyage-embeddings"}


async def _record_embedding_usage(model: str, tokens: int) -> None:
    """Make query-embedding spend visible - it was the one paid call nothing recorded.

    Even with every LLM call served by the local GPU, each grounded plan embeds its
    query with a hosted model, so "local = $0.00" was not true. It lands in the SAME two
    ledgers as LLM spend (tp_llm_cost_usd and the Redis daily key), because a divergence
    between those two is exactly what the runbook treats as "one ledger is lying". It
    stays OUT of a run's own cost_usd, which attributes the LLM venue that answered.
    """
    # Imported at CALL time on purpose. tp_core.control -> tp_core.llm.circuit runs the
    # tp_core.llm package __init__, whose gateway imports tp_core.control again: a cycle
    # that only bites when control is imported FIRST - which a module-level import here
    # would do, breaking `import tp_retrieval.embedder` outright.
    from tp_core.control import record_spend

    cost = tokens * _PRICE_PER_MTOK.get(model, 0.0) / 1_000_000
    record_venue_usage(EMBEDDING_VENUE.get(model, "embeddings"), tokens, 0, cost)
    await record_spend(cost)


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
        usage = getattr(resp, "usage", None)
        await _record_embedding_usage(self.model, int(getattr(usage, "total_tokens", 0) or 0))
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
        await _record_embedding_usage(self.model, int(getattr(result, "total_tokens", 0) or 0))
        return [list(v) for v in result.embeddings]


def get_embedder(settings: Settings | None = None) -> Embedder:
    """Voyage iff a key is configured, else OpenAI — both at the pinned 1024-d."""
    cfg = settings or get_settings()
    if cfg.voyage_api_key:
        return VoyageEmbedder(cfg.voyage_api_key)
    return OpenAIEmbedder(cfg.openai_api_key)
