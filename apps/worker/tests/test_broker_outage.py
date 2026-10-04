"""Celery's own reconnect attempts are counted as ``redis_error``.

The broker and the result backend are Redis. During an outage with no traffic, these
retries are the worker's only Redis activity - logged by Celery, counted by nothing, so a
quiet outage left ``tp_errors_total`` flat (found 2026-09-29).
"""

from __future__ import annotations

import logging

import tp_worker.celery_app  # noqa: F401  -- installs the filter, as the worker does
from prometheus_client import REGISTRY

CONSUMER = logging.getLogger("celery.worker.consumer.consumer")
BACKEND = logging.getLogger("celery.backends.redis")


def _redis_errors() -> float:
    return REGISTRY.get_sample_value("tp_errors_total", {"type": "redis_error"}) or 0.0


def test_broker_and_backend_reconnect_attempts_are_counted() -> None:
    before = _redis_errors()
    # The exact templates celery 5.6 logs (consumer.py CONNECTION_ERROR / CONNECTION_RETRY,
    # backends/redis.py E_LOST).
    CONSUMER.error("consumer: Cannot connect to %s: %s.\n%s\n", "redis://redis:6379/0",
                   "Error 111 connecting to redis:6379", "Trying again in 2.00 seconds... (1/100)")
    CONSUMER.warning("consumer: Connection to broker lost. "
                     "Trying to re-establish the connection...")
    BACKEND.error("Connection to Redis lost: Retry (%s/%s) %s.", 1, 20, "in 1.00 second")
    assert _redis_errors() == before + 3


def test_ordinary_celery_lines_are_not_counted() -> None:
    before = _redis_errors()
    CONSUMER.info("Connected to redis://redis:6379/0")
    CONSUMER.warning("an unrelated warning")
    assert _redis_errors() == before
