"""Provider adapters: normalize each vendor SDK to one ``complete`` interface.

The Anthropic path uses the native SDK (full feature parity for later steps);
OpenAI and Groq use their OpenAI-compatible chat-completions APIs. Every adapter
re-raises SDK exceptions as Retryable/NonRetryable so the gateway can decide
whether to fall back. All three are Stainless SDKs and share exception shapes
(``APITimeoutError`` / ``APIConnectionError`` / ``APIStatusError.status_code``).
"""

from __future__ import annotations

from types import ModuleType
from typing import NoReturn, Protocol, runtime_checkable

import anthropic
import groq
import openai
from anthropic import AsyncAnthropic
from groq import AsyncGroq
from openai import AsyncOpenAI

from tp_core.exceptions import NonRetryableProviderError, RetryableProviderError
from tp_core.llm.models import cost_usd
from tp_core.llm.types import LLMResponse, Message, Provider, Tier, Usage

_RETRYABLE_STATUS = {408, 409, 429}


def _classify_and_raise(exc: Exception, sdk: ModuleType, provider: Provider) -> NoReturn:
    """Re-raise an SDK exception as Retryable or NonRetryable."""
    timeout_err = getattr(sdk, "APITimeoutError", ())
    conn_err = getattr(sdk, "APIConnectionError", ())
    status_err = getattr(sdk, "APIStatusError", ())
    retryable = False
    if isinstance(exc, (timeout_err, conn_err)):
        retryable = True
    elif isinstance(exc, status_err):
        code = int(getattr(exc, "status_code", 0))
        retryable = code in _RETRYABLE_STATUS or code >= 500
    message = f"{provider.value} call failed: {type(exc).__name__}: {exc}"
    if retryable:
        raise RetryableProviderError(message) from exc
    raise NonRetryableProviderError(message) from exc


@runtime_checkable
class LLMProvider(Protocol):
    provider: Provider

    async def complete(
        self, messages: list[Message], model: str, tier: Tier, *, max_tokens: int
    ) -> LLMResponse: ...


def _as_oai_messages(messages: list[Message]) -> list[dict[str, str]]:
    return [{"role": m.role, "content": m.content} for m in messages]


class OpenAIProvider:
    provider = Provider.OPENAI

    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)

    async def complete(
        self, messages: list[Message], model: str, tier: Tier, *, max_tokens: int
    ) -> LLMResponse:
        try:
            resp = await self._client.chat.completions.create(
                model=model,
                messages=_as_oai_messages(messages),  # type: ignore[arg-type]
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - re-classified immediately
            _classify_and_raise(exc, openai, self.provider)
        choice = resp.choices[0]
        u = resp.usage
        cached = 0
        if u is not None:
            details = getattr(u, "prompt_tokens_details", None)
            cached = int(getattr(details, "cached_tokens", 0) or 0)
        prompt_tokens = u.prompt_tokens if u else 0
        completion_tokens = u.completion_tokens if u else 0
        return LLMResponse(
            text=choice.message.content or "",
            provider=self.provider,
            model=model,
            tier=tier,
            usage=Usage(
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                cached_input_tokens=cached,
                cost_usd=cost_usd(model, prompt_tokens, completion_tokens),
            ),
            finish_reason=choice.finish_reason,
        )


class GroqProvider:
    provider = Provider.GROQ

    def __init__(self, api_key: str) -> None:
        self._client = AsyncGroq(api_key=api_key)

    async def complete(
        self, messages: list[Message], model: str, tier: Tier, *, max_tokens: int
    ) -> LLMResponse:
        try:
            resp = await self._client.chat.completions.create(
                model=model,
                messages=_as_oai_messages(messages),  # type: ignore[arg-type]
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - re-classified immediately
            _classify_and_raise(exc, groq, self.provider)
        choice = resp.choices[0]
        u = resp.usage
        prompt_tokens = u.prompt_tokens if u else 0
        completion_tokens = u.completion_tokens if u else 0
        return LLMResponse(
            text=choice.message.content or "",
            provider=self.provider,
            model=model,
            tier=tier,
            usage=Usage(
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                cost_usd=cost_usd(model, prompt_tokens, completion_tokens),
            ),
            finish_reason=choice.finish_reason,
        )


class AnthropicProvider:
    provider = Provider.ANTHROPIC

    def __init__(self, api_key: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)

    async def complete(
        self, messages: list[Message], model: str, tier: Tier, *, max_tokens: int
    ) -> LLMResponse:
        system = "\n\n".join(m.content for m in messages if m.role == "system") or None
        convo = [{"role": m.role, "content": m.content} for m in messages if m.role != "system"]
        try:
            if system is not None:
                resp = await self._client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=convo,  # type: ignore[arg-type]
                )
            else:
                resp = await self._client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=convo,  # type: ignore[arg-type]
                )
        except Exception as exc:  # noqa: BLE001 - re-classified immediately
            _classify_and_raise(exc, anthropic, self.provider)
        text = "".join(getattr(block, "text", "") for block in resp.content)
        u = resp.usage
        return LLMResponse(
            text=text,
            provider=self.provider,
            model=model,
            tier=tier,
            usage=Usage(
                input_tokens=u.input_tokens,
                output_tokens=u.output_tokens,
                cached_input_tokens=int(getattr(u, "cache_read_input_tokens", 0) or 0),
                cost_usd=cost_usd(model, u.input_tokens, u.output_tokens),
            ),
            finish_reason=resp.stop_reason,
        )
