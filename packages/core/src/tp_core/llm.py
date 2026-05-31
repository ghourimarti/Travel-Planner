"""LLM gateway: a thin, testable wrapper over LiteLLM.

One async entry point, ``acomplete()``, that:

* selects a model by **tier** (``cheap`` / ``default``),
* tries providers in preference order **Groq -> OpenAI -> Anthropic** (Decision 4),
  falling back to the next candidate on any provider error,
* **skips** candidates whose API key is not configured (so dev with only a Groq
  key works), and **fails loudly** when no provider is configured,
* returns usage + best-effort cost as an :class:`LLMResult` (the seam Step 9 uses
  for budgets / Prometheus).

We use an explicit fallback loop rather than LiteLLM's ``Router`` — it is easier
to test and reason about, and matches Decision 21 (own the simple control flow).
``Router`` remains the upgrade path if we later need cross-key load balancing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import litellm
from litellm import acompletion

from tp_core.exceptions import CustomException
from tp_core.logging import get_logger
from tp_core.settings import get_settings

logger = get_logger(__name__)

# tier -> ordered candidate models (provider preference: Groq -> OpenAI -> Anthropic)
MODEL_TIERS: dict[str, list[str]] = {
    "cheap": [
        "groq/llama-3.1-8b-instant",
        "gpt-4o-mini",
        "anthropic/claude-haiku-4-5",
    ],
    "default": [
        "groq/llama-3.3-70b-versatile",
        "gpt-4o",
        "anthropic/claude-sonnet-4-6",
    ],
}

def _provider_of(model: str) -> str:
    if model.startswith("groq/"):
        return "groq"
    if model.startswith("anthropic/"):
        return "anthropic"
    return "openai"


@dataclass(slots=True)
class LLMResult:
    """Outcome of an LLM call, including usage and best-effort cost."""

    text: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float | None
    latency_ms: float
    fell_back: bool


async def acomplete(
    messages: list[dict[str, Any]],
    *,
    tier: str = "default",
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = None,
) -> LLMResult:
    """Complete ``messages`` using the given tier, with provider fallback."""
    if tier not in MODEL_TIERS:
        raise CustomException(f"unknown tier {tier!r}; expected one of {list(MODEL_TIERS)}")

    settings = get_settings()
    candidates = [
        model
        for model in MODEL_TIERS[tier]
        if settings.api_key(_provider_of(model)) is not None
    ]
    if not candidates:
        raise CustomException(
            f"no LLM provider configured for tier {tier!r}; "
            "set GROQ_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY"
        )

    last_error: Exception | None = None
    for index, model in enumerate(candidates):
        provider = _provider_of(model)
        api_key = settings.api_key(provider)
        call_kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "api_key": api_key,
            "temperature": temperature,
        }
        if max_tokens is not None:
            call_kwargs["max_tokens"] = max_tokens
        if tools is not None:
            call_kwargs["tools"] = tools

        start = time.perf_counter()
        try:
            response = await acompletion(**call_kwargs)
        except Exception as exc:  # provider error -> try the next candidate
            last_error = exc
            logger.warning(
                "LLM call failed on %s (%s); falling back", model, exc.__class__.__name__
            )
            continue

        latency_ms = (time.perf_counter() - start) * 1000.0
        usage = response.usage
        try:
            cost: float | None = litellm.completion_cost(completion_response=response)
        except Exception:  # unknown/new model pricing -> best-effort
            cost = None

        return LLMResult(
            text=response.choices[0].message.content or "",
            model=model,
            provider=provider,
            prompt_tokens=getattr(usage, "prompt_tokens", 0),
            completion_tokens=getattr(usage, "completion_tokens", 0),
            total_tokens=getattr(usage, "total_tokens", 0),
            cost_usd=cost,
            latency_ms=latency_ms,
            fell_back=index > 0,
        )

    raise CustomException(f"all LLM providers failed for tier {tier!r}", last_error)
