"""Structured JSON logging to stdout (12-factor, container/OTel-friendly).

Replaces the portfolio app's file logger (which wrote to ``./logs`` and never
reached the log pipeline). Emits one JSON object per line on stdout; bound
context (e.g. ``run_id``, ``sub_agent``) set via ``structlog.contextvars``
carries through to every downstream log call — important for tracing the
multi-agent runs added in later steps.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import TextIO, cast

import structlog
from opentelemetry import trace
from structlog.typing import EventDict, Processor, WrappedLogger

# Conservative PII patterns (GDPR hygiene, S12b): emails and long digit runs (phone/card).
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_DIGITS_RE = re.compile(r"\b\d[\d\s-]{8,}\d\b")
_REDACTED = "[redacted]"


def _add_trace_context(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Attach the current OTel trace/span id so logs join up with traces (S11a)."""
    ctx = trace.get_current_span().get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


def _scrub(value: str) -> str:
    return _DIGITS_RE.sub(_REDACTED, _EMAIL_RE.sub(_REDACTED, value))


def _redact_pii(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Mask emails / phone-like digit runs in string values so PII never reaches logs (S12b)."""
    for key, value in event_dict.items():
        if isinstance(value, str):
            event_dict[key] = _scrub(value)
    return event_dict


def configure_logging(
    level: str = "INFO",
    *,
    json_logs: bool = True,
    stream: TextIO | None = None,
) -> None:
    """Configure structlog once, at process start.

    Args:
        level: Minimum level name (DEBUG/INFO/WARNING/ERROR).
        json_logs: JSON when True (prod), human-readable console when False (local).
        stream: Output stream; defaults to ``sys.stdout``. Injectable for tests.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    out: TextIO = stream if stream is not None else sys.stdout

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_trace_context,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _redact_pii,  # last before rendering: scrub PII from the fully-built event
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(),
    ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(file=out),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound logger. Call ``configure_logging()`` once beforehand."""
    return cast("structlog.stdlib.BoundLogger", structlog.get_logger(name))
