"""FastAPI surface (S9a/S9c): async run dispatch + status + live progress stream.

``/plan`` and ``/trip`` persist a run, enqueue a Celery task BY NAME (so the API never
imports the worker/agent stack), and return a ``run_id`` (202). ``/runs/{id}`` reports
status + result; ``/runs/{id}/stream`` streams the agent trace as SSE while it runs.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel
from tp_agents import PlanRequest, TripRequest
from tp_core.auth import LOCAL_PRINCIPAL, AuthError, Principal, verify_token
from tp_core.celery import celery_app
from tp_core.control import planning_enabled
from tp_core.db import dispose_engine, init_models
from tp_core.events import subscribe
from tp_core.metrics import record_dispatch, render
from tp_core.ratelimit import allow_request
from tp_core.runs import RunRecord, RunStatus, create_run, get_run
from tp_core.settings import get_settings
from tp_core.tracing import init_tracing


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_tracing("tp-api")
    with suppress(Exception):  # propagate trace context onto enqueued Celery tasks
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        CeleryInstrumentor().instrument()  # type: ignore[no-untyped-call]
    await init_models()
    yield
    await dispose_engine()


app = FastAPI(title="AI Travel Planner API", version="0.3.0", lifespan=lifespan)
with suppress(Exception):  # auto request spans; best-effort so a bad agent never blocks boot
    FastAPIInstrumentor.instrument_app(app)

_TERMINAL = {RunStatus.succeeded.value, RunStatus.failed.value}


class RunAccepted(BaseModel):
    run_id: str
    status: str = "queued"


_bearer = HTTPBearer(auto_error=False)


async def get_principal(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    """Authenticate the caller (fail-closed). Returns a local principal when auth is off."""
    if not get_settings().auth_required:
        return LOCAL_PRINCIPAL
    if creds is None:
        raise HTTPException(status_code=401, detail="missing bearer token")
    try:
        return verify_token(creds.credentials)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


async def _enforce_rate_limit(endpoint: str, tenant_id: str) -> None:
    """429 when the tenant is over its per-minute budget (fail-open if Redis is down)."""
    if not await allow_request(tenant_id, limit=get_settings().rate_limit_per_min):
        record_dispatch(endpoint, "rate_limited")
        raise HTTPException(status_code=429, detail="rate limit exceeded")


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> Response:
    payload, content_type = render()
    return Response(content=payload, media_type=content_type)


@app.post("/plan", response_model=RunAccepted, status_code=202)
async def create_plan(
    request: PlanRequest, principal: Annotated[Principal, Depends(get_principal)]
) -> RunAccepted:
    if not await planning_enabled():
        record_dispatch("plan", "disabled")
        raise HTTPException(status_code=503, detail="planning is temporarily disabled")
    await _enforce_rate_limit("plan", principal.tenant_id)
    run_id = await create_run("plan", request, tenant_id=principal.tenant_id)
    celery_app.send_task("tp_worker.tasks.plan_task", args=[run_id])
    record_dispatch("plan", "queued")
    return RunAccepted(run_id=run_id)


@app.post("/trip", response_model=RunAccepted, status_code=202)
async def create_trip(
    request: TripRequest, principal: Annotated[Principal, Depends(get_principal)]
) -> RunAccepted:
    if not await planning_enabled():
        record_dispatch("trip", "disabled")
        raise HTTPException(status_code=503, detail="planning is temporarily disabled")
    await _enforce_rate_limit("trip", principal.tenant_id)
    run_id = await create_run("trip", request, tenant_id=principal.tenant_id)
    celery_app.send_task("tp_worker.tasks.trip_task", args=[run_id])
    record_dispatch("trip", "queued")
    return RunAccepted(run_id=run_id)


@app.get("/runs/{run_id}", response_model=RunRecord)
async def get_run_status(
    run_id: str, principal: Annotated[Principal, Depends(get_principal)]
) -> RunRecord:
    record = await get_run(run_id, tenant_id=principal.tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    return record


@app.get("/runs/{run_id}/stream")
async def stream_run(
    run_id: str, principal: Annotated[Principal, Depends(get_principal)]
) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        record = await get_run(run_id, tenant_id=principal.tenant_id)
        if record is None:  # unknown or owned by another tenant — same response, no probing
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
