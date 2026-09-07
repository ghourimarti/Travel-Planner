"""A per-venue circuit breaker for the serving chain.

WHY
---
Failover alone is not enough. Without a breaker, a dead local engine is retried
on EVERY request: each call pays the connect timeout before falling through to
Groq, so one free leg being down becomes added latency on 100% of traffic. The
breaker converts "down" from a per-request cost into a one-off cost paid once
per cooldown window.

STATES
------
    CLOSED     normal; calls go through
    OPEN       recent consecutive failures >= threshold; leg is SKIPPED
    HALF_OPEN  cooldown elapsed; ONE probe is allowed through

A probe that succeeds closes the breaker; a probe that fails re-opens it for
another cooldown. That single-probe rule is what stops a recovering engine from
being hit by the full request rate the instant it comes back.

KEYED BY str, NOT BY Provider. ``Provider`` is a ``StrEnum``, so every existing venue
call site keeps working untouched — but the same breaker now also protects INFRA
dependencies ("redis", "postgres"), which are not venues and never will be. One
breaker implementation, one set of semantics, two kinds of dependency: a second
copy for infra would drift from this one the first time either was tuned.

SCOPE: in-process and per-worker, deliberately. A shared (Redis) breaker would
be strictly better at coordinating replicas, but it puts a network call on the
hot path of every request and creates a dependency that can itself fail open or
closed. Per-process is the honest trade at this scale; the cost is that N
workers each pay one probe per cooldown, which is bounded and small.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import StrEnum


class BreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class _Leg:
    failures: int = 0
    opened_at: float | None = None
    probing: bool = False


@dataclass
class CircuitBreaker:
    """Tracks consecutive failures per venue and skips legs that are open."""

    threshold: int = 3
    cooldown_s: float = 30.0
    _legs: dict[str, _Leg] = field(default_factory=dict)

    def _leg(self, provider: str) -> _Leg:
        return self._legs.setdefault(provider, _Leg())

    def state(self, provider: str, *, now: float | None = None) -> BreakerState:
        leg = self._leg(provider)
        if leg.opened_at is None:
            return BreakerState.CLOSED
        t = time.monotonic() if now is None else now
        if t - leg.opened_at >= self.cooldown_s:
            return BreakerState.HALF_OPEN
        return BreakerState.OPEN

    def allows(self, provider: str, *, now: float | None = None) -> bool:
        """True if a call may be attempted on this venue right now.

        HALF_OPEN admits exactly ONE caller: the first one flips `probing`, and
        everyone else is refused until that probe reports back. Letting the whole
        request rate through the moment the cooldown expires is how a recovering
        engine gets knocked straight back over.
        """
        st = self.state(provider, now=now)
        if st is BreakerState.CLOSED:
            return True
        if st is BreakerState.OPEN:
            return False
        leg = self._leg(provider)
        if leg.probing:
            return False
        leg.probing = True
        return True

    def record_success(self, provider: str) -> None:
        self._legs[provider] = _Leg()  # fully reset: closed, no failures, not probing

    def record_failure(self, provider: str, *, now: float | None = None) -> None:
        leg = self._leg(provider)
        leg.failures += 1
        leg.probing = False
        if leg.failures >= self.threshold:
            leg.opened_at = time.monotonic() if now is None else now

    def snapshot(self, *, now: float | None = None) -> dict[str, str]:
        """Every KNOWN leg's state, for logging and metrics.

        Reports every leg it knows about, not just the one that moved: a gauge
        written only when a venue is touched leaves untouched legs reporting a
        stale value forever.

        `now` is threaded through for the same reason the other methods take it:
        mixing an injected clock with `time.monotonic()` makes a just-opened leg
        read as half-open, which is a real reporting bug and not only a test
        inconvenience.
        """
        return {str(p): self.state(p, now=now).value for p in self._legs}


# --- infra dependencies ------------------------------------------------------
#
# Same breaker, different failure posture. A venue being open means "use the next
# leg"; Redis being open means "skip the cache and answer anyway", and Postgres being
# open means "serve without history". Neither infra breaker may ever fail a request.
_INFRA: dict[str, CircuitBreaker] = {}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def infra_breaker(name: str) -> CircuitBreaker:
    """Process-wide breaker for an infra dependency ("redis" | "postgres").

    Thresholds come from the environment rather than Settings, for the reason
    control.py documents: these sit on the request path, and a missing provider key
    must not turn a cache lookup into a config error.
    """
    if name not in _INFRA:
        prefix = name.upper()
        _INFRA[name] = CircuitBreaker(
            threshold=_env_int(f"{prefix}_CIRCUIT_FAILURE_THRESHOLD", 3),
            cooldown_s=_env_float(f"{prefix}_CIRCUIT_COOLDOWN_SECONDS", 30.0),
        )
    return _INFRA[name]


def reset_infra_breakers() -> None:
    """Drop all infra breaker state.

    The registry is process-wide on purpose — one Redis, one breaker — but that makes
    it leak between tests: a suite that provokes a Redis failure leaves the breaker
    OPEN, and the next test's cache is skipped for reasons it never asked for. That is
    exactly how it should behave in production and exactly what a test must not
    inherit, so the seam is here rather than in the semantics.
    """
    _INFRA.clear()
