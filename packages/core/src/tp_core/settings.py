"""Typed, environment-loaded application settings — fail-fast.

Replaces the portfolio app's ``os.getenv("GROQ_API_KEY")`` that silently
returned ``None``. A missing or malformed *required* key raises
:class:`~tp_core.exceptions.ConfigError` at startup, not at the first provider
call. Optional provider keys are declared now and wired in the step that needs
them (Groq/OpenAI in S2, Voyage in S6).
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
DEFAULT_MAX_COST_USD = 0.30  # per-itinerary budget cap + eval gate (Phase-1 ceiling)


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

    # --- LLM providers (Decision 4, amended in S2: only an OpenAI key is available) ---
    # Required now: the primary provider must have a key, or the app fails fast.
    openai_api_key: str = Field(min_length=1)
    # Optional fallback rungs — a tier uses them only if the key is present:
    anthropic_api_key: str | None = None
    groq_api_key: str | None = None
    voyage_api_key: str | None = None  # S6 embeddings: used iff set, else OpenAI (same 1024-d)

    # --- vector store (S6) ---
    qdrant_url: str | None = None  # set for a real Qdrant server; else local embedded mode
    qdrant_path: str = ".qdrant_local"

    # --- persistence / async dispatch (S9) ---
    database_url: str = DEFAULT_DATABASE_URL  # sqlite+aiosqlite local; postgresql+asyncpg in prod
    redis_url: str = DEFAULT_REDIS_URL  # Celery broker + result backend

    # --- cost controls (S10b) ---
    max_cost_usd: float = DEFAULT_MAX_COST_USD  # per-itinerary cap + eval budget gate

    # --- observability: Langfuse (S11b) — spans export there iff both keys are set ---
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings, raising :class:`ConfigError` on any bad key.

    Cached so configuration is parsed and validated exactly once per process.
    """
    try:
        return Settings()
    except ValidationError as exc:
        raise ConfigError(f"Invalid or missing configuration:\n{exc}") from exc
