"""OpenTelemetry tracing setup (S11a, Decision 13).

One process-wide TracerProvider. Spans are always created (cheap) but only EXPORTED
when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set, so local dev + tests need no collector and a
broken collector never touches the request path. ``init_tracing`` is idempotent and
best-effort; ``get_tracer`` returns a no-op tracer until a provider is installed.
"""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Tracer

_initialized = False


def init_tracing(service_name: str = "ai-travel-planner") -> None:
    """Install a TracerProvider once per process (best-effort; never raises)."""
    global _initialized
    if _initialized:
        return
    _initialized = True
    try:
        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)
    except Exception:  # tracing must never fail the app
        pass


def get_tracer() -> Tracer:
    """Return the tracer (a no-op until a provider is installed)."""
    return trace.get_tracer("tp")
