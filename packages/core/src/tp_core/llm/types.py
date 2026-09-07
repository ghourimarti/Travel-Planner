"""Boundary types for the LLM gateway (Pydantic at the seam — no vendor types leak)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


class Tier(StrEnum):
    """Capability/cost tier. The gateway maps a tier to a provider+model chain."""

    CHEAP = "cheap"
    MID = "mid"
    FRONTIER = "frontier"


class Provider(StrEnum):
    """A serving VENUE, not a vendor.

    The local venues are split by ENGINE because that is the identity the chain
    is configured in: `local-sglang` and `local-vllm` are different legs that
    fail independently of each other (a crash, an OOM, a bad build) even though
    they share a GPU and therefore fail together when the card dies.
    """

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    LOCAL_VLLM = "local-vllm"
    LOCAL_SGLANG = "local-sglang"


Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
    role: Role
    content: str


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0  # prompt-cache reads — billed ~10x cheaper than fresh input
    cost_usd: float = 0.0


class LLMResponse(BaseModel):
    text: str
    provider: Provider
    model: str
    tier: Tier
    usage: Usage
    finish_reason: str | None = None
