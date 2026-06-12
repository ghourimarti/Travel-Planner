"""Settings contract: typed load + fail-fast on missing/invalid required keys."""

from __future__ import annotations

import pytest
from tp_core.exceptions import ConfigError
from tp_core.settings import get_settings


def test_loads_with_required_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    settings = get_settings()
    assert settings.anthropic_api_key == "sk-test-123"
    # Defaults applied for unset optional config.
    assert settings.app_env == "local"
    assert settings.log_level == "INFO"
    assert settings.groq_api_key is None


def test_fail_fast_on_missing_required_key() -> None:
    # ANTHROPIC_API_KEY is unset (conftest clears it) and no .env is read.
    with pytest.raises(ConfigError):
        get_settings()


def test_fail_fast_on_invalid_enum(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    monkeypatch.setenv("LOG_LEVEL", "VERBOSE")  # not a valid Literal value
    with pytest.raises(ConfigError):
        get_settings()


def test_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    assert get_settings() is get_settings()  # same cached instance
