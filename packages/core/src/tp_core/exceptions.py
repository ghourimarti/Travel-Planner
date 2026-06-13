"""Exception hierarchy for the AI Travel Planner.

A single base class lets callers catch every application error by type, while
specific subclasses let them distinguish configuration failures (fatal, at
startup) from provider/tool failures (handled, at runtime) added in later steps.
"""

from __future__ import annotations


class TravelPlannerError(Exception):
    """Base class for all application errors."""


class ConfigError(TravelPlannerError):
    """Configuration is missing or invalid. Raised fail-fast at startup."""


class ProviderError(TravelPlannerError):
    """An LLM (or external) provider call failed."""


class RetryableProviderError(ProviderError):
    """Transient failure (timeout, rate limit, 5xx) — safe to retry / fall back."""


class NonRetryableProviderError(ProviderError):
    """Permanent failure (bad request, auth, not found) — do not fall back."""
