"""Structured JSON logging to stdout (12-factor, container/OTel-friendly).

Replaces the portfolio app's file logger (which wrote to ``./logs`` and never
reached the log pipeline). Emits one JSON object per line on stdout; bound
context (e.g. ``run_id``, ``sub_agent``) set via ``structlog.contextvars``
carries through to every downstream log call — important for tracing the
multi-agent runs added in later steps.
"""

from __future__ import annotations

import logging
import sys
from typing import TextIO, cast

import structlog
from structlog.typing import Processor


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
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
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
