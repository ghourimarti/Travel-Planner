"""Shared Celery app (Decision 11).

Broker + result backend come from ``REDIS_URL`` in the environment — read here
directly (not via ``get_settings``) so this module imports WITHOUT a provider key,
exactly as the gateway/retriever are built lazily in the API. The worker registers
tasks against this app; the API only ``send_task``s by name, so the API process
never imports the task code or the agent stack it pulls in.
"""

from __future__ import annotations

import os

from celery import Celery

from tp_core.settings import DEFAULT_REDIS_URL


def make_celery() -> Celery:
    """Build the Celery app from REDIS_URL with sane long-job defaults."""
    url = os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)
    app = Celery("tp", broker=url, backend=url)
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_acks_late=True,  # redeliver if a worker dies mid-task (Decision 21)
        worker_prefetch_multiplier=1,  # fair dispatch for long-running jobs
        task_time_limit=300,  # hard per-run ceiling, seconds (Decision 20)
        task_soft_time_limit=270,
    )
    return app


celery_app = make_celery()
