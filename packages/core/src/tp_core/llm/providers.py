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
import httpx
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


class LocalEngineProvider:
    """vLLM or SGLang over its OpenAI-compatible API.

    Both engines expose ``/v1/chat/completions``, so the OpenAI SDK drives them
    unchanged — only ``base_url`` differs. That is the whole reason the chain can
    treat a self-hosted GPU as just another venue.

    THE MODEL IS NOT A PARAMETER HERE. A hosted venue offers a catalog and the
    tier picks from it; a local engine serves exactly ONE model — whichever was
    loaded at startup — so the model travels with the provider instance. Asking
    a local engine for a model it has not loaded returns 404, the leg fails, and
    you silently pay a hosted venue for every token while believing you are
    self-hosting.

    COST IS ALWAYS RECORDED, INCLUDING 0.0. Self-hosted inference is free at the
    margin, but omitting the number is not the same as reporting zero: a spend
    dashboard that receives nothing cannot distinguish "free" from "not
    measured".
    """

    def __init__(
        self,
        provider: Provider,
        base_url: str,
        model: str,
        *,
        connect_timeout_s: float = 2.0,
        read_timeout_s: float = 120.0,
    ) -> None:
        self.provider = provider
        self.model = model
        # A SHORT CONNECT timeout on purpose. When the engine is down the socket
        # is refused immediately, but when the box is unreachable a default
        # timeout makes every request pay the full wait before failing over —
        # which turns a dead free leg into latency on every single call.
        self._client = AsyncOpenAI(
            api_key="local-engine-needs-no-key",
            base_url=base_url,
            timeout=httpx.Timeout(read_timeout_s, connect=connect_timeout_s),
            max_retries=0,  # the gateway owns retry/fallback policy
        )

    async def complete(
        self, messages: list[Message], model: str, tier: Tier, *, max_tokens: int
    ) -> LLMResponse:
        # `model` is ignored by design — see the class docstring. The loaded
        # model wins, and it is what gets reported back.
        served = self.model
        try:
            resp = await self._client.chat.completions.create(
                model=served,
                messages=_as_oai_messages(messages),  # type: ignore[arg-type]
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - re-classified immediately
            _classify_and_raise(exc, openai, self.provider)
        choice = resp.choices[0]
        u = resp.usage
        prompt_tokens = u.prompt_tokens if u else 0
        completion_tokens = u.completion_tokens if u else 0
        return LLMResponse(
            text=choice.message.content or "",
            provider=self.provider,
            model=served,
            tier=tier,
            usage=Usage(
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                cached_input_tokens=0,
                cost_usd=0.0,  # explicit: self-hosted, and 0.0 != unmeasured
            ),
            finish_reason=choice.finish_reason,
        )
