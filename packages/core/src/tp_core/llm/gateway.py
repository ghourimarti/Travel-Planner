"""The LLM gateway: one provider-agnostic ``complete`` with tiering + fallback.

Callers never import a vendor SDK — they ask for a *tier* and the gateway
resolves it to a provider/model chain, walking the chain on transient failures
while refusing to fall back on client errors (a bad request fails the same way
everywhere, so retrying it elsewhere just burns money). Cost and every attempt
are structured-logged.
"""

from __future__ import annotations

import asyncio
import time

from tp_core.control import record_spend
from tp_core.exceptions import (
    ConfigError,
    NonRetryableProviderError,
    ProviderError,
    RetryableProviderError,
)
from tp_core.llm.circuit import CircuitBreaker
from tp_core.llm.models import TIER_ROUTING
from tp_core.llm.providers import (
    AnthropicProvider,
    GroqProvider,
    LLMProvider,
    LocalEngineProvider,
    OpenAIProvider,
)
from tp_core.llm.types import LLMResponse, Message, Provider, Tier
from tp_core.llm.venues import ChainLeg, model_for, parse_chain, raw_chain_for_tier
from tp_core.logging import get_logger
from tp_core.metrics import (
    record_circuit,
    record_error,
    record_llm,
    record_venue_latency,
    record_venue_usage,
)
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
        chains: dict[Tier, list[ChainLeg]] | None = None,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        if not providers:
            raise ConfigError("LLMGateway requires at least one configured provider.")
        self._providers = providers
        self._timeout_s = timeout_s
        # None (or a tier absent from the dict) = legacy behaviour: the hardcoded
        # order in TIER_ROUTING. A configured chain takes over for that tier only.
        # Keeping both means adding local venues cannot change an existing
        # deployment until someone opts in.
        self._chains = chains or {}
        self._breaker = breaker or CircuitBreaker()

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

        # Local engines: a leg with no URL is SKIPPED, never a runtime error, so
        # a chain can name an engine before the GPU box exists.
        if cfg.vllm_url:
            providers[Provider.LOCAL_VLLM] = LocalEngineProvider(
                Provider.LOCAL_VLLM, cfg.vllm_url, cfg.vllm_model
            )
        if cfg.sglang_url:
            providers[Provider.LOCAL_SGLANG] = LocalEngineProvider(
                Provider.LOCAL_SGLANG, cfg.sglang_url, cfg.sglang_model
            )

        per_tier = {
            Tier.CHEAP: cfg.chain_cheap,
            Tier.MID: cfg.chain_mid,
            Tier.FRONTIER: cfg.chain_frontier,
        }
        chains: dict[Tier, list[ChainLeg]] = {}
        for tier in Tier:
            raw = raw_chain_for_tier(
                tier, baseline=cfg.serving_chain, per_tier=per_tier
            )
            if not raw:
                continue  # this tier keeps the legacy TIER_ROUTING order
            legs = parse_chain(raw, default_engine=cfg.serving_engine)
            chains[tier] = legs
            missing = [leg.venue.value for leg in legs if leg.venue not in providers]
            if missing:
                # A WARNING naming the venue, never a silent downgrade. Being
                # quietly served by a hosted venue while believing you are
                # self-hosting is the failure this line exists to prevent.
                _log.warning(
                    "llm_chain_leg_skipped", tier=tier.value, venues=",".join(missing)
                )
        breaker = CircuitBreaker(
            threshold=cfg.circuit_failure_threshold,
            cooldown_s=cfg.circuit_cooldown_seconds,
        )
        return cls(providers, timeout_s=timeout_s, chains=chains, breaker=breaker)

    def _resolve_chain(self, tier: Tier) -> list[tuple[Provider, str]]:
        """Ordered (venue, model) legs for a tier.

        With SERVING_CHAIN set, ORDER COMES FROM CONFIG and the model is resolved
        per venue: a local engine reports the model it actually loaded, a hosted
        venue takes the tier's catalog entry. Without it, the legacy per-tier
        order is used unchanged.
        """
        configured = self._chains.get(tier)
        if configured is None:
            return [(p, m) for (p, m) in TIER_ROUTING[tier] if p in self._providers]
        legs: list[tuple[Provider, str]] = []
        for leg in configured:
            adapter = self._providers.get(leg.venue)
            if adapter is None:
                continue
            # Precedence: an explicit `venue:model` override, else the model a
            # local engine actually loaded, else this tier's catalog entry.
            model = (
                leg.model
                or getattr(adapter, "model", None)
                or model_for(leg.venue, tier)
            )
            if model is None:
                continue
            legs.append((leg.venue, model))
        return legs

    async def complete(
        self, messages: list[Message], tier: Tier, *, max_tokens: int = 1024
    ) -> LLMResponse:
        chain = self._resolve_chain(tier)
        if not chain:
            raise ConfigError(f"No configured provider for tier '{tier.value}'.")

        with get_tracer().start_as_current_span("llm.complete") as span:
            span.set_attribute("llm.tier", tier.value)
            last_error: Exception | None = None
            for provider, model in chain:
                # An OPEN breaker skips the leg without paying its timeout. This
                # is the difference between a dead free leg costing one probe per
                # cooldown and it costing every single request.
                if not self._breaker.allows(provider):
                    _log.debug("llm_leg_skipped_open", venue=provider.value)
                    continue
                adapter = self._providers[provider]
                leg_started = time.perf_counter()
                try:
                    resp = await asyncio.wait_for(
                        adapter.complete(messages, model, tier, max_tokens=max_tokens),
                        timeout=self._timeout_s,
                    )
                except NonRetryableProviderError:
                    record_error("llm_non_retryable")
                    _log.error(
                        "llm_non_retryable",
                        tier=tier.value,
                        provider=provider.value,
                        model=model,
                    )
                    raise
                except (RetryableProviderError, TimeoutError) as exc:
                    last_error = exc
                    # Only TRANSIENT faults count against the breaker. A 400 is
                    # our bad request and fails identically everywhere, so
                    # opening a venue for it would punish the venue for our bug.
                    self._breaker.record_failure(provider)
                    record_circuit(self._breaker.snapshot())
                    record_error(
                        "llm_timeout" if isinstance(exc, TimeoutError) else "llm_transient"
                    )
                    _log.warning(
                        "llm_fallback",
                        tier=tier.value,
                        provider=provider.value,
                        model=model,
                        error=str(exc),
                    )
                    continue
                # Latency attributed to the venue that actually answered. Run duration
                # averages over whichever leg served, so it cannot show local vs hosted.
                record_venue_latency(provider.value, time.perf_counter() - leg_started)
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
                # "generation" (model + token usage + cost). Never prompt text.
                span.set_attribute("gen_ai.system", provider.value)
                span.set_attribute("gen_ai.request.model", model)
                span.set_attribute("gen_ai.usage.input_tokens", resp.usage.input_tokens)
                span.set_attribute("gen_ai.usage.output_tokens", resp.usage.output_tokens)
                span.set_attribute("gen_ai.usage.cost", round(resp.usage.cost_usd, 6))
                self._breaker.record_success(provider)
                span.set_attribute("llm.venue", provider.value)
                record_llm(tier.value, provider.value)
                # Attribute tokens and spend to the venue that ACTUALLY served,
                # not to the first leg in the chain. Crediting a hosted answer to
                # the free local engine is how a silent failover stays invisible.
                record_venue_usage(
                    provider.value,
                    resp.usage.input_tokens,
                    resp.usage.output_tokens,
                    resp.usage.cost_usd,
                )
                # Accumulate DAILY spend for the budget breaker in control.py.
                #
                # This is the only place the real per-call cost exists, and until now
                # NOTHING called record_spend() — so spend_today() read a key nobody
                # wrote, always returned 0.0, and DAILY_SPEND_LIMIT_USD could never
                # trip. The unit tests passed because they mocked spend_today, which
                # is precisely how a dead control keeps looking alive.
                #
                # Recorded even at 0.0: a self-hosted day must read zero, not absent.
                await record_spend(resp.usage.cost_usd)
                record_circuit(self._breaker.snapshot())
                return resp

            raise ProviderError(
                f"All providers exhausted for tier '{tier.value}'."
            ) from last_error
