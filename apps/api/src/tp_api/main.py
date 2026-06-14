"""FastAPI surface (S9a): async run dispatch + status.

``/plan`` and ``/trip`` no longer block on the planner — they persist a run, enqueue
a Celery task BY NAME (so the API never imports the worker/task code), and return a
``run_id``. ``/runs/{id}`` reports status + result. The graph executes on the worker
(``apps/worker``). The schema is created on startup (lifespan); Alembic arrives with
auth in S12.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from tp_agents import PlanRequest, TripRequest
from tp_core.celery import celery_app
from tp_core.db import dispose_engine, init_models
from tp_core.runs import RunRecord, create_run, get_run


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_models()
    yield
    await dispose_engine()


app = FastAPI(title="AI Travel Planner API", version="0.2.0", lifespan=lifespan)


class RunAccepted(BaseModel):
    run_id: str
    status: str = "queued"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/plan", response_model=RunAccepted, status_code=202)
async def create_plan(request: PlanRequest) -> RunAccepted:
    run_id = await create_run("plan", request)
    celery_app.send_task("tp_worker.tasks.plan_task", args=[run_id])
    return RunAccepted(run_id=run_id)


@app.post("/trip", response_model=RunAccepted, status_code=202)
async def create_trip(request: TripRequest) -> RunAccepted:
    run_id = await create_run("trip", request)
    celery_app.send_task("tp_worker.tasks.trip_task", args=[run_id])
    return RunAccepted(run_id=run_id)


@app.get("/runs/{run_id}", response_model=RunRecord)
async def get_run_status(run_id: str) -> RunRecord:
    record = await get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    return record
