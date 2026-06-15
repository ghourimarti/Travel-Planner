"""FastAPI surface (S9a/S9c): async run dispatch + status + live progress stream.

``/plan`` and ``/trip`` persist a run, enqueue a Celery task BY NAME (so the API never
imports the worker/agent stack), and return a ``run_id`` (202). ``/runs/{id}`` reports
status + result; ``/runs/{id}/stream`` streams the agent trace as SSE while it runs.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from tp_agents import PlanRequest, TripRequest
from tp_core.celery import celery_app
from tp_core.db import dispose_engine, init_models
from tp_core.events import subscribe
from tp_core.runs import RunRecord, RunStatus, create_run, get_run


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_models()
    yield
    await dispose_engine()


app = FastAPI(title="AI Travel Planner API", version="0.3.0", lifespan=lifespan)

_TERMINAL = {RunStatus.succeeded.value, RunStatus.failed.value}


class RunAccepted(BaseModel):
    run_id: str
    status: str = "queued"


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


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


@app.get("/runs/{run_id}/stream")
async def stream_run(run_id: str) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        record = await get_run(run_id)
        if record is None:
            yield _sse({"type": "error", "detail": "run not found"})
            return
        yield _sse({"type": "status", "status": record.status})
        if record.status in _TERMINAL:  # already finished — send result, don't wait for the bus
            yield _sse({"type": record.status, "result": record.result, "error": record.error})
            return
        async for event in subscribe(run_id):
            yield _sse(event.model_dump())
            if event.type in ("done", "failed"):
                break

    return StreamingResponse(events(), media_type="text/event-stream")
