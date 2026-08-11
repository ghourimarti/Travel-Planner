"""Shared Celery app.

Broker + result backend come from ``REDIS_URL`` in the environment — read here
directly (not via ``get_settings``) so this module imports WITHOUT a provider key,
exactly as the gateway/retriever are built lazily in the API. The worker registers
tasks against this app; the API only ``send_task``s by name, so the API process
never imports the task code or the agent stack it pulls in.
"""

from __future__ import annotations

import os
import sys

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
        task_acks_late=True,  # redeliver if a worker dies mid-task
        worker_prefetch_multiplier=1,  # fair dispatch for long-running jobs
        task_time_limit=300,  # hard per-run ceiling, seconds
        task_soft_time_limit=270,
        # How long a task may sit unacknowledged after a worker dies before the broker
        # hands it to someone else. `task_acks_late` only redelivers once this expires,
        # and Kombu's Redis default is 3600s — an hour of a run sitting in `running`
        # after a hard crash. INVARIANT: keep this above the longest a task can actually
        # run, or a task still legitimately executing gets handed to a second worker and
        # runs (and bills) twice. The default clears `task_time_limit`; lower it only
        # where runs are known to be short (e.g. a demo box) to shorten crash recovery.
        broker_transport_options={
            "visibility_timeout": int(os.environ.get("CELERY_VISIBILITY_TIMEOUT", "360"))
        },
        result_expires=86400,
        # Emit task lifecycle events so a monitor (Flower) can show queue depth,
        # per-task runtime, retries and failures. Set here rather than as a `-E`
        # flag on one deployment's worker command, so compose, Helm and k8s all
        # inherit it. `task_send_sent_event` covers the publisher (the API), which
        # makes a task visible the moment it is queued, not only once it starts.
        worker_send_task_events=True,
        task_send_sent_event=True,
    )
    if sys.platform == "win32":
        # The prefork (billiard) pool is unreliable on Windows — its pool workers
        # die with WinError 5/6 and tasks never run. Solo executes tasks in the main
        # process, which is correct for local dev/demo here; prod runs on Linux/prefork.
        app.conf.worker_pool = "solo"
    return app


celery_app = make_celery()
