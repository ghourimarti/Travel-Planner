"""Celery tasks: run the planner graph off the request thread (Decision 11).

Each sync task drives the async LangGraph via ``asyncio.run`` (a fresh loop per
task). The request is loaded from Postgres by ``run_id`` — never passed through
Celery — so there's nothing to (de)serialize but a string. A failure is recorded on
the run AND re-raised so Celery (acks_late) also marks the task failed.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache

from tp_agents import PlanRequest, TripRequest, plan, plan_trip
from tp_agents.nodes import PoiRetriever
from tp_core.celery import celery_app
from tp_core.runs import get_run, mark_failed, mark_running, mark_succeeded


@lru_cache
def _retriever() -> PoiRetriever | None:
    """Build the corpus retriever once per worker process; ``None`` if unavailable."""
    try:
        from tp_retrieval import get_retriever

        return get_retriever()
    except Exception:  # no key / no Qdrant -> live-tool fallback (Decision 21)
        return None


async def _run_plan(run_id: str) -> None:
    record = await get_run(run_id)
    if record is None:
        return
    await mark_running(run_id)
    try:
        itinerary = await plan(
            PlanRequest.model_validate(record.request), retriever=_retriever(), run_id=run_id
        )
        await mark_succeeded(
            run_id, itinerary, cost_usd=itinerary.cost_usd, warnings=itinerary.warnings
        )
    except Exception as exc:
        await mark_failed(run_id, f"{type(exc).__name__}: {exc}")
        raise


async def _run_trip(run_id: str) -> None:
    record = await get_run(run_id)
    if record is None:
        return
    await mark_running(run_id)
    try:
        trip = await plan_trip(
            TripRequest.model_validate(record.request), retriever=_retriever(), run_id=run_id
        )
        await mark_succeeded(run_id, trip, cost_usd=trip.cost_usd, warnings=trip.warnings)
    except Exception as exc:
        await mark_failed(run_id, f"{type(exc).__name__}: {exc}")
        raise


@celery_app.task(name="tp_worker.tasks.plan_task")
def plan_task(run_id: str) -> None:
    asyncio.run(_run_plan(run_id))


@celery_app.task(name="tp_worker.tasks.trip_task")
def trip_task(run_id: str) -> None:
    asyncio.run(_run_trip(run_id))
