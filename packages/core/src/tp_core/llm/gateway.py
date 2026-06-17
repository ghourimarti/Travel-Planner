"""The LLM gateway: one provider-agnostic ``complete`` with tiering + fallback.

Callers never import a vendor SDK — they ask for a *tier* and the gateway
resolves it to a provider/model chain (Decision 4), walking the chain on
transient failures (Decision 21) while refusing to fall back on client errors.
Cost and every attempt are structured-logged for the observability step.
"""

from __future__ import annotations

import asyncio

from tp_core.exceptions import (
    ConfigError,
    NonRetryableProviderError,
    ProviderError,
    RetryableProviderError,
)
from tp_core.llm.models import TIER_ROUTING
from tp_core.llm.providers import (
    AnthropicProvider,
    GroqProvider,
    LLMProvider,
    OpenAIProvider,
)
from tp_core.llm.types import LLMResponse, Message, Provider, Tier
from tp_core.logging import get_logger
from tp_core.metrics import record_llm
from tp_core.settings import Settings, get_settings
from tp_core.tracing import get_tracer

_log = get_logger("tp_core.llm.gateway")
_DEFAULT_TIMEOUT_S = 60.0


class LLMGateway:
    """Routes a tier to a provider/model chain with cross-provider fallback."""

    def __init__(
        self,
        providers: dict[Provider, LLMProvider],
        *,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        if not providers:
            raise ConfigError("LLMGateway requires at least one configured provider.")
        self._providers = providers
        self._timeout_s = timeout_s

    @classmethod
    def from_settings(
        cls, settings: Settings | None = None, *, timeout_s: float = _DEFAULT_TIMEOUT_S
    ) -> LLMGateway:
        """Build a gateway with whichever providers have a configured API key."""
        cfg = settings or get_settings()
        providers: dict[Provider, LLMProvider] = {
            Provider.OPENAI: OpenAIProvider(cfg.openai_api_key)
        }
        if cfg.anthropic_api_key:
            providers[Provider.ANTHROPIC] = AnthropicProvider(cfg.anthropic_api_key)
        if cfg.groq_api_key:
            providers[Provider.GROQ] = GroqProvider(cfg.groq_api_key)
        return cls(providers, timeout_s=timeout_s)

    async def complete(
        self, messages: list[Message], tier: Tier, *, max_tokens: int = 1024
    ) -> LLMResponse:
        chain = [(p, m) for (p, m) in TIER_ROUTING[tier] if p in self._providers]
        if not chain:
            raise ConfigError(f"No configured provider for tier '{tier.value}'.")

        with get_tracer().start_as_current_span("llm.complete") as span:
            span.set_attribute("llm.tier", tier.value)
            last_error: Exception | None = None
            for provider, model in chain:
                adapter = self._providers[provider]
                try:
                    resp = await asyncio.wait_for(
                        adapter.complete(messages, model, tier, max_tokens=max_tokens),
                        timeout=self._timeout_s,
                    )
                except NonRetryableProviderError:
                    _log.error(
                        "llm_non_retryable",
                        tier=tier.value,
                        provider=provider.value,
                        model=model,
                    )
                    raise
                except (RetryableProviderError, TimeoutError) as exc:
                    last_error = exc
                    _log.warning(
                        "llm_fallback",
                        tier=tier.value,
                        provider=provider.value,
                        model=model,
                        error=str(exc),
                    )
                    continue
                _log.info(
                    "llm_complete",
                    tier=tier.value,
                    provider=provider.value,
                    model=model,
                    input_tokens=resp.usage.input_tokens,
                    output_tokens=resp.usage.output_tokens,
                    cost_usd=round(resp.usage.cost_usd, 6),
                )
                span.set_attribute("llm.provider", provider.value)
                span.set_attribute("llm.model", model)
                span.set_attribute("llm.input_tokens", resp.usage.input_tokens)
                span.set_attribute("llm.output_tokens", resp.usage.output_tokens)
                span.set_attribute("llm.cost_usd", round(resp.usage.cost_usd, 6))
                # GenAI semantic conventions → Langfuse renders this span as a
                # "generation" (model + token usage + cost). No prompt text (DG-11e).
                span.set_attribute("gen_ai.system", provider.value)
                span.set_attribute("gen_ai.request.model", model)
                span.set_attribute("gen_ai.usage.input_tokens", resp.usage.input_tokens)
                span.set_attribute("gen_ai.usage.output_tokens", resp.usage.output_tokens)
                span.set_attribute("gen_ai.usage.cost", round(resp.usage.cost_usd, 6))
                record_llm(tier.value, provider.value)
                return resp

            raise ProviderError(
                f"All providers exhausted for tier '{tier.value}'."
            ) from last_error
