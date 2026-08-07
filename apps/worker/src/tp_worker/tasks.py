"""Celery tasks: run the planner graph off the request thread.

Each sync task drives the async LangGraph via ``asyncio.run`` (a fresh loop per
task). The request is loaded from Postgres by ``run_id`` — never passed through
Celery — so there's nothing to (de)serialize but a string. A failure is recorded on
the run AND re-raised so Celery (acks_late) also marks the task failed.
"""

from __future__ import annotations

import asyncio
import time
from functools import lru_cache
from typing import Any

from tp_agents import PlanRequest, TripRequest, plan, plan_trip
from tp_agents.nodes import PoiRetriever
from tp_core.celery import celery_app
from tp_core.events import run_publisher
from tp_core.metrics import record_run
from tp_core.runs import get_run, mark_failed, mark_running, mark_succeeded


@lru_cache
def _retriever() -> PoiRetriever | None:
    """Build the corpus retriever once per worker process; ``None`` if unavailable."""
    try:
        from tp_retrieval import get_retriever

        return get_retriever()
    except Exception:  # no key / no Qdrant -> fall back to live tools
        return None


async def _run_plan(run_id: str) -> None:
    record = await get_run(run_id)
    if record is None:
        return
    await mark_running(run_id)
    start = time.monotonic()
    async with run_publisher(run_id) as emit:

        async def on_event(node: str, delta: Any, *, city: str | None = None) -> None:
            await emit("node", node=node, city=city)

        try:
            itinerary = await plan(
                PlanRequest.model_validate(record.request),
                retriever=_retriever(),
                run_id=run_id,
                tenant_id=record.tenant_id,
                on_event=on_event,
            )
            await mark_succeeded(
                run_id, itinerary, cost_usd=itinerary.cost_usd, warnings=itinerary.warnings
            )
            record_run("succeeded", time.monotonic() - start, itinerary.cost_usd)
            await emit("done")
        except Exception as exc:
            record_run("failed", time.monotonic() - start, 0.0)
            await mark_failed(run_id, f"{type(exc).__name__}: {exc}")
            await emit("failed", detail=str(exc))
            raise


async def _run_trip(run_id: str) -> None:
    record = await get_run(run_id)
    if record is None:
        return
    await mark_running(run_id)
    start = time.monotonic()
    async with run_publisher(run_id) as emit:

        async def on_event(node: str, delta: Any, *, city: str | None = None) -> None:
            await emit("node", node=node, city=city)

        try:
            trip = await plan_trip(
                TripRequest.model_validate(record.request),
                retriever=_retriever(),
                run_id=run_id,
                tenant_id=record.tenant_id,
                on_event=on_event,
            )
            await mark_succeeded(run_id, trip, cost_usd=trip.cost_usd, warnings=trip.warnings)
            record_run("succeeded", time.monotonic() - start, trip.cost_usd)
            await emit("done")
        except Exception as exc:
            record_run("failed", time.monotonic() - start, 0.0)
            await mark_failed(run_id, f"{type(exc).__name__}: {exc}")
            await emit("failed", detail=str(exc))
            raise


@celery_app.task(name="tp_worker.tasks.plan_task")
def plan_task(run_id: str) -> None:
    asyncio.run(_run_plan(run_id))


@celery_app.task(name="tp_worker.tasks.trip_task")
def trip_task(run_id: str) -> None:
    asyncio.run(_run_trip(run_id))
