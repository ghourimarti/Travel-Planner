"""Gateway contract (mocked providers): tiering, fallback, no-fallback, timeout, exhaustion."""

from __future__ import annotations

import asyncio

import pytest
from tp_core.exceptions import (
    NonRetryableProviderError,
    ProviderError,
    RetryableProviderError,
)
from tp_core.llm.gateway import LLMGateway
from tp_core.llm.types import LLMResponse, Message, Provider, Tier, Usage

MSGS = [Message(role="user", content="hi")]


class _FakeProvider:
    def __init__(
        self,
        provider: Provider,
        *,
        raise_exc: Exception | None = None,
        sleep_s: float = 0.0,
    ):
        self.provider = provider
        self._raise = raise_exc
        self._sleep = sleep_s
        self.calls = 0

    async def complete(self, messages, model, tier, *, max_tokens):  # noqa: ANN001, ANN201
        self.calls += 1
        if self._sleep:
            await asyncio.sleep(self._sleep)
        if self._raise is not None:
            raise self._raise
        return LLMResponse(text="ok", provider=self.provider, model=model, tier=tier, usage=Usage())


def test_tier_selects_openai_primary() -> None:
    gw = LLMGateway({Provider.OPENAI: _FakeProvider(Provider.OPENAI)})
    resp = asyncio.run(gw.complete(MSGS, Tier.MID))
    assert resp.provider is Provider.OPENAI
    assert resp.model == "gpt-4o"


def test_falls_back_on_retryable() -> None:
    primary = _FakeProvider(Provider.OPENAI, raise_exc=RetryableProviderError("429"))
    fallback = _FakeProvider(Provider.ANTHROPIC)
    gw = LLMGateway({Provider.OPENAI: primary, Provider.ANTHROPIC: fallback})
    resp = asyncio.run(gw.complete(MSGS, Tier.FRONTIER))
    assert resp.provider is Provider.ANTHROPIC
    assert primary.calls == 1
    assert fallback.calls == 1


def test_no_fallback_on_non_retryable() -> None:
    primary = _FakeProvider(Provider.OPENAI, raise_exc=NonRetryableProviderError("400"))
    fallback = _FakeProvider(Provider.ANTHROPIC)
    gw = LLMGateway({Provider.OPENAI: primary, Provider.ANTHROPIC: fallback})
    with pytest.raises(NonRetryableProviderError):
        asyncio.run(gw.complete(MSGS, Tier.FRONTIER))
    assert fallback.calls == 0


def test_timeout_triggers_fallback() -> None:
    slow = _FakeProvider(Provider.OPENAI, sleep_s=0.20)
    fast = _FakeProvider(Provider.ANTHROPIC)
    gw = LLMGateway({Provider.OPENAI: slow, Provider.ANTHROPIC: fast}, timeout_s=0.01)
    resp = asyncio.run(gw.complete(MSGS, Tier.FRONTIER))
    assert resp.provider is Provider.ANTHROPIC


def test_all_providers_exhausted_raises() -> None:
    primary = _FakeProvider(Provider.OPENAI, raise_exc=RetryableProviderError("529"))
    gw = LLMGateway({Provider.OPENAI: primary})
    with pytest.raises(ProviderError):
        asyncio.run(gw.complete(MSGS, Tier.CHEAP))
