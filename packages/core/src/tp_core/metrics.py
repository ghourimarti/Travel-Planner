"""Prometheus metrics (S11c, Decision 13): RED + cost as scrapable time-series.

One module-level set of metric objects on the default registry; thin ``record_*``
helpers keep ``prometheus_client`` out of the call sites. Each process (API, worker)
exposes its own metrics, so Prometheus scrapes them as SEPARATE targets (pull model) —
counters populate in whichever process owns the work. Labels are bounded enums only;
high-cardinality identifiers (run_id, city, user) stay on traces, never on metrics.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# Buckets tuned to the Phase-1 NFRs: latency p50 20s / p95 45s / p99 75s, cost ≤ $0.30.
_DURATION_BUCKETS = (0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 45.0, 60.0, 75.0, 120.0)
_COST_BUCKETS = (0.001, 0.005, 0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0)

# Counter names omit the ``_total`` suffix — prometheus_client appends it on exposition.
RUNS = Counter("tp_runs", "Planner runs by terminal status.", ["status"])
RUN_DURATION = Histogram(
    "tp_run_duration_seconds", "Wall-clock seconds per planner run.", buckets=_DURATION_BUCKETS
)
RUN_COST = Histogram(
    "tp_run_cost_usd", "Cost (USD) per succeeded itinerary.", buckets=_COST_BUCKETS
)
LLM_CALLS = Counter("tp_llm_calls", "Successful LLM completions.", ["tier", "provider"])
CRITIC_REVISIONS = Counter("tp_critic_revisions", "Critic-triggered corrective re-composes.")
DISPATCH = Counter("tp_dispatch", "API run dispatches.", ["endpoint", "outcome"])


def record_run(status: str, duration_s: float, cost_usd: float) -> None:
    """Record a finished run: status counter + duration, and cost on success."""
    RUNS.labels(status=status).inc()
    RUN_DURATION.observe(duration_s)
    if status == "succeeded":
        RUN_COST.observe(cost_usd)


def record_llm(tier: str, provider: str) -> None:
    LLM_CALLS.labels(tier=tier, provider=provider).inc()


def record_revision() -> None:
    CRITIC_REVISIONS.inc()


def record_dispatch(endpoint: str, outcome: str) -> None:
    DISPATCH.labels(endpoint=endpoint, outcome=outcome).inc()


def render() -> tuple[bytes, str]:
    """Return ``(payload, content_type)`` for a ``/metrics`` response."""
    return generate_latest(), CONTENT_TYPE_LATEST
