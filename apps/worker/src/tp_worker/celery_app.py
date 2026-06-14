"""Worker entrypoint: ``celery -A tp_worker.celery_app worker``.

Re-exports the shared Celery app and imports the tasks module so the tasks
register. Ensures the run-state tables exist on worker startup (idempotent
``create_all`` — DG2).
"""

from __future__ import annotations

import asyncio

from celery import signals
from tp_core.celery import celery_app

from tp_worker import tasks  # noqa: F401  -- registers plan_task / trip_task

__all__ = ["celery_app"]


@signals.worker_init.connect
def _ensure_schema(**_: object) -> None:
    from tp_core.db import init_models

    asyncio.run(init_models())
