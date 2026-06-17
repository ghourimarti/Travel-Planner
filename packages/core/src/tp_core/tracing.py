"""OpenTelemetry tracing setup (S11a/S11b, Decision 13).

One process-wide TracerProvider. Spans are always created (cheap) but only EXPORTED
when a destination is configured, so local dev + tests need no collector and a broken
collector never touches the request path. Two optional export targets, both best-effort:
a generic OTLP endpoint (``OTEL_EXPORTER_OTLP_ENDPOINT``, S11a) and Langfuse (its
OTel-native ingest, enabled when both ``LANGFUSE_*`` keys are set, S11b). ``init_tracing``
is idempotent; ``get_tracer`` returns a no-op tracer until a provider is installed.
"""

from __future__ import annotations

import base64
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Tracer

_initialized = False


def _add_langfuse_exporter(provider: TracerProvider) -> None:
    """Export spans to Langfuse via its OTLP-native ingest, iff both keys are set (S11b)."""
    from tp_core.settings import get_settings

    cfg = get_settings()
    if not (cfg.langfuse_public_key and cfg.langfuse_secret_key):
        return
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    token = base64.b64encode(
        f"{cfg.langfuse_public_key}:{cfg.langfuse_secret_key}".encode()
    ).decode()
    exporter = OTLPSpanExporter(
        endpoint=f"{cfg.langfuse_host.rstrip('/')}/api/public/otel/v1/traces",
        headers={"Authorization": f"Basic {token}"},
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))


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
        _add_langfuse_exporter(provider)
        trace.set_tracer_provider(provider)
    except Exception:  # nosec B110 - tracing is best-effort and must never fail the app
        pass


def get_tracer() -> Tracer:
    """Return the tracer (a no-op until a provider is installed)."""
    return trace.get_tracer("tp")
