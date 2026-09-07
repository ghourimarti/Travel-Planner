"""Typed, environment-loaded application settings — fail-fast.

Config is read once, validated, and typed — never scattered ``os.getenv`` calls
that silently return ``None``. A missing or malformed *required* key raises
:class:`~tp_core.exceptions.ConfigError` at startup rather than at the first
provider call. Optional provider keys stay unset-friendly, so a partial
configuration degrades gracefully instead of failing.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from tp_core.exceptions import ConfigError

# Infra bootstrap defaults — read directly by db.py / celery.py (without the LLM
# settings) so persistence + dispatch can stand up WITHOUT a provider key.
DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./tp_runs.db"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_MAX_COST_USD = 0.30  # per-itinerary budget ceiling: runtime cap + eval gate


class Settings(BaseSettings):
    """Application configuration loaded from environment / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- app ---
    app_env: Literal["local", "dev", "staging", "prod"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # --- LLM providers (OpenAI primary; the rest are optional fallback rungs) ---
    # Required now: the primary provider must have a key, or the app fails fast.
    openai_api_key: str = Field(min_length=1)
    # Optional fallback rungs — a tier uses them only if the key is present:
    anthropic_api_key: str | None = None
    groq_api_key: str | None = None
    voyage_api_key: str | None = None  # embeddings: used iff set, else OpenAI (same 1024-d)

    # --- local inference venues (self-hosted GPU) ---
    # SERVING_CHAIN is the whole failover policy in one line, tried left to
    # right. EMPTY = legacy behaviour: the hardcoded per-tier order in
    # models.TIER_ROUTING. Setting it takes over, so this is additive and the
    # existing deployment does not change until someone opts in.
    #
    # Entries are `venue` or `venue-engine`; `local` alone resolves through
    # serving_engine. A leg with no URL/key is SKIPPED, never a runtime error.
    serving_chain: str = ""
    serving_engine: Literal["vllm", "sglang"] = "sglang"

    # PER-CALL-POINT OVERRIDES (Decision 24). A tier that sets its own chain uses
    # it; every other tier falls back to serving_chain, then to the legacy table.
    #
    # This matters because one loaded 7-8B model serves EVERY tier identically -
    # it cannot be three different models. Putting `local` first on FRONTIER hands
    # multi-city planning and the critic to a 7B, which is exactly where itinerary
    # quality is decided. Leaving CHAIN_FRONTIER hosted keeps that deliberate.
    chain_cheap: str = ""
    chain_mid: str = ""
    chain_frontier: str = ""

    # A local engine serves exactly ONE model — whichever was loaded — so the URL
    # and the model travel together. Empty URL = that leg is skipped, which is
    # how a chain can name an engine before the GPU box exists.
    vllm_url: str | None = None
    vllm_model: str = "Qwen/Qwen2.5-7B-Instruct-AWQ"
    sglang_url: str | None = None
    sglang_model: str = "Qwen/Qwen2.5-7B-Instruct-AWQ"

    # --- circuit breaker over chain legs ---
    # A leg that has failed this many times in a row is SKIPPED for the cooldown
    # rather than retried on every request. Without this, a dead local engine
    # costs every single request its connect timeout before failover — the free
    # leg being down turns into latency on 100% of traffic.
    circuit_failure_threshold: int = 3
    circuit_cooldown_seconds: float = 30.0

    # --- vector store ---
    qdrant_url: str | None = None  # set for a real Qdrant server; else local embedded mode
    qdrant_path: str = ".qdrant_local"

    # --- persistence / async dispatch ---
    database_url: str = DEFAULT_DATABASE_URL  # sqlite+aiosqlite local; postgresql+asyncpg in prod
    redis_url: str = DEFAULT_REDIS_URL  # Celery broker + result backend

    # --- cost controls ---
    max_cost_usd: float = DEFAULT_MAX_COST_USD  # per-itinerary cap + eval budget gate

    # llm_enabled is a FLOOR, not a toggle. Shipped False, no runtime Redis value can
    # turn generation back on: an operator's static decision outranks a stale flag.
    # The Redis switch (`planning:enabled`) can only ever DISABLE, never re-enable.
    llm_enabled: bool = True
    # Rolling per-DAY spend ceiling across every run. max_cost_usd above is per
    # ITINERARY and cannot answer "how much went to the paid leg while the GPU was
    # down". 0.0 disables the breaker, which is today's behaviour.
    daily_spend_limit_usd: float = 0.0
    # Fraction of the daily limit that raises a warning before the breaker bites.
    spend_soft_alert_ratio: float = 0.8

    # --- abuse defence: two windows, two scopes ---
    # 0 disables a check entirely, so every default below is exactly today's behaviour
    # (per-minute per-tenant only). A limit that silently starts refusing traffic on
    # upgrade would be a behaviour change smuggled in as configuration.
    rate_limit_per_day: int = 0
    rate_limit_ip_per_min: int = 0
    # Proxy hops to trust in X-Forwarded-For. 0 = trust NONE and use the socket peer.
    # Getting this wrong is not a small mistake: every per-IP limit is defeated by a
    # forged header, and the limit still LOOKS enforced on the dashboard.
    trusted_proxy_hops: int = 0

    # --- retrieval depth (was hardcoded k=20 / top_n=8 in tp_retrieval) ---
    retrieval_top_k: int = 20  # candidates fetched before reranking
    rerank_top_k: int = 8  # passages kept after reranking

    # --- cache invalidation by VERSION KEY, never by hand ---
    # Bumping one of these orphans the old entries and lets their own TTL reap them.
    # The alternative is FLUSHDB, which also discards every unrelated cached value.
    prompt_version: str = "v1"  # bump when a prompt changes
    corpus_version: str = "v1"  # bump after a re-ingest
    index_version: str = "v1"  # bump after an embedding-model change

    # --- infra circuit breakers (separate from the serving-venue breaker) ---
    # Losing Postgres DEGRADES the service (history off) rather than stopping it, so
    # this breaker exists to stop hammering a dead database, not to fail requests.
    postgres_circuit_failure_threshold: int = 3
    postgres_circuit_cooldown_seconds: float = 30.0
    # Redis loss is fail-OPEN: bypass the cache and keep answering.
    redis_circuit_failure_threshold: int = 3
    redis_circuit_cooldown_seconds: float = 30.0

    # --- observability: Langfuse — spans export there iff both keys are set ---
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # --- observability: Prometheus — worker exposes /metrics on this port ---
    worker_metrics_port: int = 9200

    # --- security / Auth0 — fail-closed; auth0 keys required when enabled ---
    auth_enabled: bool | None = None  # None → enforced unless app_env == "local"
    auth0_domain: str | None = None
    auth0_audience: str | None = None

    @property
    def auth_required(self) -> bool:
        """Whether endpoints require a valid token (explicit flag, else by env)."""
        return self.auth_enabled if self.auth_enabled is not None else self.app_env != "local"

    # --- abuse defense — per-tenant requests/minute (0 disables) ---
    rate_limit_per_min: int = 60


@lru_cache
def get_settings() -> Settings:
    """Return cached settings, raising :class:`ConfigError` on any bad key.

    Cached so configuration is parsed and validated exactly once per process.
    """
    try:
        return Settings()
    except ValidationError as exc:
        raise ConfigError(f"Invalid or missing configuration:\n{exc}") from exc
