"""Unit tests for typed settings (no .env, no network)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tp_core.settings import Settings, get_settings


def test_defaults() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.environment == "development"
    assert s.log_level == "INFO"
    assert s.groq_api_key is None


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.environment == "production"
    assert s.log_level == "DEBUG"  # validator upper-cases
    assert s.groq_api_key == "test-key"


def test_invalid_log_level_fails_fast() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, log_level="BOGUS")  # type: ignore[call-arg]


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
