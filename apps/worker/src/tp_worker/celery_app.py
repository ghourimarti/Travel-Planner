"""Worker entrypoint: ``celery -A tp_worker.celery_app worker``.

Re-exports the shared Celery app and imports the tasks module so the tasks
register. Ensures the run-state tables exist on worker startup (idempotent
``create_all`` — DG2).
"""

from __future__ import annotations

import asyncio
from contextlib import suppress

from celery import signals
from tp_core.celery import celery_app

from tp_worker import tasks  # noqa: F401  -- registers plan_task / trip_task

__all__ = ["celery_app"]


@signals.worker_init.connect
def _on_worker_init(**_: object) -> None:
    from tp_core.tracing import init_tracing

    init_tracing("tp-worker")
    with suppress(Exception):  # continue the trace started by the API's enqueue
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        CeleryInstrumentor().instrument()  # type: ignore[no-untyped-call]
    with suppress(Exception):  # expose this worker as its own Prometheus scrape target
        from prometheus_client import start_http_server
        from tp_core.settings import get_settings

        start_http_server(get_settings().worker_metrics_port)
    from tp_core.db import init_models

    asyncio.run(init_models())
