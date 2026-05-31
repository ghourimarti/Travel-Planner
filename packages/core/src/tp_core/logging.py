"""Logging setup.

Logs to **stdout** as a stream (12-factor) rather than to a file as the demo did
— so containers/Kubernetes (and the ELK/Filebeat stack) collect logs without the
app owning log files. Structured (structlog) logging is layered in at Step 12.
"""

from __future__ import annotations

import logging
import sys

_configured = False


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once, idempotently."""
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger, ensuring logging is configured."""
    configure_logging()
    return logging.getLogger(name)
