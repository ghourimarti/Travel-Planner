"""Unit tests for typed settings (hermetic via conftest: no real .env / env)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tp_core.settings import Settings, get_settings


def test_defaults() -> None:
    s = Settings()
    assert s.environment == "development"
    assert s.log_level == "INFO"
    assert s.groq_api_key is None
    assert s.api_key("groq") is None


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    s = Settings()
    assert s.environment == "production"
    assert s.log_level == "DEBUG"  # validator upper-cases
    assert s.api_key("groq") == "test-key"


def test_secret_key_is_masked_in_repr() -> None:
    s = Settings(groq_api_key="super-secret")
    assert "super-secret" not in repr(s)  # SecretStr masks it
    assert s.api_key("groq") == "super-secret"  # but readable on demand


def test_invalid_log_level_fails_fast() -> None:
    with pytest.raises(ValidationError):
        Settings(log_level="BOGUS")


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
