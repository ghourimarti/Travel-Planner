"""Worker entrypoint: ``celery -A tp_worker.celery_app worker``.

Re-exports the shared Celery app and imports the tasks module so the tasks
register. Ensures the run-state tables exist on worker startup (idempotent
``create_all``).
"""

from __future__ import annotations

import asyncio
import os
from contextlib import suppress

from celery import signals
from tp_core.celery import celery_app

from tp_worker import tasks  # noqa: F401  -- registers plan_task / trip_task

__all__ = ["celery_app"]


def _start_metrics_server() -> None:
    """Expose this worker as its own Prometheus scrape target.

    Celery's prefork pool runs tasks in CHILD processes, so counters they increment live
    in the child's memory and never reach this parent -- which is the process that serves
    ``/metrics``. With ``PROMETHEUS_MULTIPROC_DIR`` set, children write mmap files and we
    must serve an *aggregating* registry instead of the default one, or every run metric
    reads 0 forever.
    """
    from prometheus_client import start_http_server
    from tp_core.metrics import metrics_registry
    from tp_core.settings import get_settings

    port = get_settings().worker_metrics_port
    registry = metrics_registry()
    if registry is not None:
        start_http_server(port, registry=registry)
    else:
        start_http_server(port)


@signals.worker_process_shutdown.connect
def _on_worker_process_shutdown(**_: object) -> None:
    """Let the aggregator drop this child's per-process files when the child exits."""
    if not os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        return
    with suppress(Exception):
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(os.getpid())  # type: ignore[no-untyped-call]


@signals.worker_init.connect
def _on_worker_init(**_: object) -> None:
    from tp_core.tracing import init_tracing

    init_tracing("tp-worker")
    with suppress(Exception):  # continue the trace started by the API's enqueue
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        CeleryInstrumentor().instrument()  # type: ignore[no-untyped-call]
    with suppress(Exception):  # expose this worker as its own Prometheus scrape target
        _start_metrics_server()
    from tp_core.db import init_models

    asyncio.run(init_models())
