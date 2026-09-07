"""Prometheus metrics: RED + cost as scrapable time-series.

One module-level set of metric objects on the default registry; thin ``record_*``
helpers keep ``prometheus_client`` out of the call sites. Each process (API, worker)
exposes its own metrics, so Prometheus scrapes them as SEPARATE targets (pull model) —
counters populate in whichever process owns the work. Labels are bounded enums only;
high-cardinality identifiers (run_id, city, user) stay on traces, never on metrics.
"""

from __future__ import annotations

import os

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)

# prometheus_client writes a per-process mmap file the instant a metric object is
# constructed -- i.e. at import time, just below. The directory must therefore already
# exist, or importing this module dies with FileNotFoundError. Under compose the path is
# a tmpfs (created by Docker, empty on every start); this makedirs keeps native runs working.
_MULTIPROC_DIR = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
if _MULTIPROC_DIR:
    os.makedirs(_MULTIPROC_DIR, exist_ok=True)

# Buckets tuned to the service targets: latency p50 20s / p95 45s / p99 75s, cost ≤ $0.30.
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
# Which SCOPE refused, not just that something did. A 429 with no scope label cannot
# distinguish "one tenant is hammering us" from "one IP is minting tenants", and those
# need opposite responses.
RATE_LIMIT_EVENTS = Counter(
    "tp_rate_limit_events", "Rate-limit decisions.", ["scope", "outcome"]
)

# --- serving venue: which leg answered, what it cost, and is it open? ---------
#
# LLM_CALLS above already carries a `provider` label, which IS the venue
# (`local-sglang`, `groq`, ...). These three add the parts it cannot express.
#
# WHY TOKENS AND COST ARE SEPARATE FROM RUN COST: tp_run_cost_usd is per
# ITINERARY. It cannot answer "how much of this month went to the paid leg
# because the GPU was down", which is the question a serving chain exists to
# make answerable.
LLM_TOKENS = Counter(
    "tp_llm_tokens", "LLM tokens by venue and direction.", ["provider", "direction"]
)
LLM_COST = Counter(
    "tp_llm_cost_usd", "LLM spend (USD) by venue.", ["provider"]
)
# 0 closed · 1 half-open · 2 open. A gauge rather than a counter because state is
# a level, not an event.
CIRCUIT_STATE = Gauge(
    "tp_venue_circuit_state",
    "Serving-venue breaker: 0=closed, 1=half_open, 2=open.",
    ["provider"],
    multiprocess_mode="mostrecent",
)

# --- pipeline shape: where time goes, what came back, and what it cost --------
#
# EVERY series below exists because a panel needs it. A metric nobody charts is
# overhead; a panel with no metric says "No data" forever, which is
# indistinguishable from "healthy and quiet" — the failure that hid a dead Groq
# rung for months.
_STAGE_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 45.0)

STAGE_DURATION = Histogram(
    "tp_stage_duration_seconds",
    "Seconds per pipeline stage (geocode | gather | compose | critic).",
    ["stage"],
    buckets=_STAGE_BUCKETS,
)
# Per-VENUE latency. tp_run_duration_seconds is per itinerary and averages over
# whatever venue happened to answer, so it cannot show that the local engine is
# slower than Groq — which is the entire question when choosing where to serve.
VENUE_LATENCY = Histogram(
    "tp_venue_latency_seconds",
    "Seconds per LLM call, by venue.",
    ["provider"],
    buckets=_STAGE_BUCKETS,
)
CACHE_EVENTS = Counter(
    "tp_cache_events", "Cache lookups by tool and result.", ["tool", "result"]
)
# What the user actually got. success/failure is too coarse: an honest "no POIs
# found" and a fully grounded itinerary are both HTTP 200, and conflating them is
# how silent quality degradation stays silent.
ITINERARY_OUTCOME = Counter(
    "tp_itinerary_outcome", "Itineraries by kind.", ["kind"]
)
ERRORS = Counter("tp_errors", "Errors by type.", ["type"])
# POIs returned per query. Zero means the itinerary is ungrounded, which the
# outcome counter records but this quantifies.
RETRIEVAL_RESULTS = Histogram(
    "tp_retrieval_results",
    "POIs returned per retrieval.",
    buckets=(0, 1, 2, 5, 8, 10, 15, 20, 30),
)

_CIRCUIT_CODES = {"closed": 0, "half_open": 1, "open": 2}


def record_venue_usage(
    provider: str, input_tokens: int, output_tokens: int, cost_usd: float
) -> None:
    """Tokens and spend for the venue that actually served the call.

    COST IS RECORDED EVEN WHEN IT IS 0.0. Self-hosted inference is free at the
    margin, and guarding this with `if cost_usd:` would mean a local engine never
    appears on a spend dashboard at all — making "free" and "not measured"
    indistinguishable, which is exactly when a silent failover goes unnoticed.
    """
    LLM_TOKENS.labels(provider=provider, direction="input").inc(input_tokens)
    LLM_TOKENS.labels(provider=provider, direction="output").inc(output_tokens)
    LLM_COST.labels(provider=provider).inc(cost_usd)


def record_circuit(states: dict[str, str]) -> None:
    """Publish EVERY known leg's breaker state.

    Writing only the leg that just moved leaves the others reporting a stale
    value forever — a dashboard that says a venue is open long after it recovered
    is worse than no dashboard, because it is believed.
    """
    for provider, state in states.items():
        CIRCUIT_STATE.labels(provider=provider).set(_CIRCUIT_CODES.get(state, 0))



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


def metrics_registry() -> CollectorRegistry | None:
    """Aggregating registry for forking servers (Celery's prefork pool).

    ``prometheus_client`` keeps counters in process memory, so values incremented in a
    forked child are invisible to the parent process that serves ``/metrics``. When
    ``PROMETHEUS_MULTIPROC_DIR`` is set, children write mmap files and this registry
    sums them at scrape time. Returns ``None`` for single-process servers (the API),
    which keep using the default registry unchanged.
    """
    if not os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        return None
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)  # type: ignore[no-untyped-call]
    return registry


def render() -> tuple[bytes, str]:
    """Return ``(payload, content_type)`` for a ``/metrics`` response."""
    registry = metrics_registry()
    payload = generate_latest(registry) if registry is not None else generate_latest()
    return payload, CONTENT_TYPE_LATEST


def record_rate_limit(scope: str, outcome: str) -> None:
    """One rate-limit decision. ``outcome`` is "allowed" or "refused"."""
    RATE_LIMIT_EVENTS.labels(scope=scope, outcome=outcome).inc()


def record_stage(stage: str, duration_s: float) -> None:
    """One pipeline stage completed."""
    STAGE_DURATION.labels(stage=stage).observe(duration_s)


def record_venue_latency(provider: str, duration_s: float) -> None:
    """One LLM call's wall time, attributed to the venue that served it."""
    VENUE_LATENCY.labels(provider=provider).observe(duration_s)


def record_cache(tool: str, result: str) -> None:
    """One cache lookup. ``result`` is "hit", "miss", or "skipped" (breaker open)."""
    CACHE_EVENTS.labels(tool=tool, result=result).inc()


def record_outcome(kind: str) -> None:
    """One finished itinerary. ``kind`` is "grounded", "degraded", or "not_found"."""
    ITINERARY_OUTCOME.labels(kind=kind).inc()


def record_error(error_type: str) -> None:
    """One error, labelled by CLASS not message — messages are unbounded cardinality."""
    ERRORS.labels(type=error_type).inc()


def record_retrieval(n_results: int) -> None:
    """How many POIs a retrieval returned (0 = ungrounded)."""
    RETRIEVAL_RESULTS.observe(n_results)
