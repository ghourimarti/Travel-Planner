"""S9a: a Celery task runs the planner off-thread and records the run.

``plan``/``plan_trip`` and the retriever are monkeypatched, so no tools/LLM/Qdrant/
key are touched; the task body is exercised in-process (the asyncio bridge).
"""

from __future__ import annotations

import asyncio

import tp_worker.tasks as tasks
from tp_agents import Itinerary, PlanRequest, TripItinerary, TripRequest
from tp_core.runs import RunStatus, create_run, get_run


def test_plan_task_succeeds(monkeypatch):
    async def fake_plan(request, *, retriever=None):
        return Itinerary(
            city=request.city, summary_markdown="ok", grounded=True, cost_usd=0.01, warnings=["w1"]
        )

    monkeypatch.setattr(tasks, "plan", fake_plan)
    monkeypatch.setattr(tasks, "_retriever", lambda: None)
    run_id = asyncio.run(create_run("plan", PlanRequest(city="Tokyo", interests=["temples"])))

    tasks.plan_task(run_id)

    rec = asyncio.run(get_run(run_id))
    assert rec is not None
    assert rec.status == RunStatus.succeeded.value
    assert rec.result is not None and rec.result["city"] == "Tokyo"
    assert rec.cost_usd == 0.01
    assert "w1" in rec.warnings


def test_plan_task_records_failure(monkeypatch):
    async def boom(request, *, retriever=None):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(tasks, "plan", boom)
    monkeypatch.setattr(tasks, "_retriever", lambda: None)
    run_id = asyncio.run(create_run("plan", PlanRequest(city="Nowhere", interests=["x"])))

    try:
        tasks.plan_task(run_id)
    except RuntimeError:
        pass  # re-raised so Celery (acks_late) also records failure

    rec = asyncio.run(get_run(run_id))
    assert rec is not None
    assert rec.status == RunStatus.failed.value
    assert "kaboom" in (rec.error or "")


def test_trip_task_succeeds(monkeypatch):
    async def fake_trip(request, *, retriever=None):
        return TripItinerary(summary_markdown="trip", cost_usd=0.05)

    monkeypatch.setattr(tasks, "plan_trip", fake_trip)
    monkeypatch.setattr(tasks, "_retriever", lambda: None)
    run_id = asyncio.run(
        create_run("trip", TripRequest(cities=["Tokyo", "Osaka"], interests=["food"]))
    )

    tasks.trip_task(run_id)

    rec = asyncio.run(get_run(run_id))
    assert rec is not None
    assert rec.status == RunStatus.succeeded.value
    assert rec.result is not None and rec.result["summary_markdown"] == "trip"
