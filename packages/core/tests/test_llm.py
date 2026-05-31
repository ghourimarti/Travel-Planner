"""Unit tests for the LLM gateway (mocked LiteLLM) + a live Groq smoke test.

Hermeticity (clean env, no real .env) is provided by conftest.hermetic_settings.
"""

from __future__ import annotations

from typing import Any

import pytest

import tp_core.llm as llm_module
from tp_core.exceptions import CustomException
from tp_core.llm import acomplete
from tp_core.settings import Settings, get_settings


def _settings(
    groq: str | None = None, openai: str | None = None, anthropic: str | None = None
) -> Settings:
    return Settings(groq_api_key=groq, openai_api_key=openai, anthropic_api_key=anthropic)


class _Msg:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Msg(content)


class _Usage:
    prompt_tokens = 10
    completion_tokens = 5
    total_tokens = 15


class _Resp:
    def __init__(self, content: str = "hi") -> None:
        self.choices = [_Choice(content)]
        self.usage = _Usage()


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    *,
    fail_for: tuple[str, ...] = (),
    record: list[str] | None = None,
) -> None:
    monkeypatch.setattr(llm_module, "get_settings", lambda: settings)

    async def _fake(**kwargs: Any) -> _Resp:
        model = kwargs["model"]
        if record is not None:
            record.append(model)
        if model in fail_for:
            raise RuntimeError(f"provider error: {model}")
        return _Resp()

    monkeypatch.setattr(llm_module, "acompletion", _fake)
    monkeypatch.setattr(llm_module.litellm, "completion_cost", lambda **_: 0.001)


async def test_default_uses_groq(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    _patch(monkeypatch, _settings(groq="g"), record=calls)
    result = await acomplete([{"role": "user", "content": "hi"}], tier="default")
    assert result.model == "groq/llama-3.3-70b-versatile"
    assert result.provider == "groq"
    assert result.fell_back is False
    assert result.total_tokens == 15
    assert result.cost_usd == 0.001
    assert calls == ["groq/llama-3.3-70b-versatile"]


async def test_cheap_tier_selects_small_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _settings(groq="g"))
    result = await acomplete([{"role": "user", "content": "hi"}], tier="cheap")
    assert result.model == "groq/llama-3.1-8b-instant"


async def test_fallback_groq_to_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    _patch(
        monkeypatch,
        _settings(groq="g", openai="o"),
        fail_for=("groq/llama-3.3-70b-versatile",),
        record=calls,
    )
    result = await acomplete([{"role": "user", "content": "hi"}], tier="default")
    assert result.model == "gpt-4o"
    assert result.provider == "openai"
    assert result.fell_back is True
    assert calls == ["groq/llama-3.3-70b-versatile", "gpt-4o"]


async def test_skips_provider_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    _patch(monkeypatch, _settings(openai="o"), record=calls)  # no groq key
    result = await acomplete([{"role": "user", "content": "hi"}], tier="default")
    assert result.model == "gpt-4o"
    assert calls == ["gpt-4o"]  # groq candidate skipped, never called


async def test_all_providers_fail_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch,
        _settings(groq="g", openai="o", anthropic="a"),
        fail_for=(
            "groq/llama-3.3-70b-versatile",
            "gpt-4o",
            "anthropic/claude-sonnet-4-6",
        ),
    )
    with pytest.raises(CustomException):
        await acomplete([{"role": "user", "content": "hi"}], tier="default")


async def test_no_provider_configured_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _settings())
    with pytest.raises(CustomException):
        await acomplete([{"role": "user", "content": "hi"}], tier="default")


async def test_unknown_tier_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _settings(groq="g"))
    with pytest.raises(CustomException):
        await acomplete([{"role": "user", "content": "hi"}], tier="bogus")


@pytest.mark.integration
async def test_live_groq_smoke() -> None:
    get_settings.cache_clear()
    if not get_settings().api_key("groq"):
        pytest.skip("GROQ_API_KEY not set in environment/.env")
    result = await acomplete(
        [{"role": "user", "content": "Reply with exactly the word: pong"}],
        tier="cheap",
    )
    assert result.text.strip()
    assert result.provider == "groq"
    assert result.total_tokens > 0
