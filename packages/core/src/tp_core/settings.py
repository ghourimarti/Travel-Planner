"""Typed application settings.

Replaces the demo's bare ``os.getenv`` config with a validated Pydantic
``BaseSettings``. Invalid config (e.g. a bad LOG_LEVEL) fails *loudly at
startup* rather than surfacing as a confusing runtime error later.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}


class Settings(BaseSettings):
    """Process configuration, loaded from environment / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Runtime
    environment: str = "development"
    log_level: str = "INFO"

    # LLM provider keys (preference order Groq -> OpenAI -> Anthropic, Decision 4).
    # Optional at this layer so imports/CI don't explode without keys; presence is
    # asserted at point-of-use by the LLM client (Step 2).
    groq_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        upper = value.upper()
        if upper not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"log_level must be one of {sorted(_VALID_LOG_LEVELS)}, got {value!r}"
            )
        return upper


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached ``Settings`` instance."""
    return Settings()
