"""FastAPI surface: async run dispatch + status + live progress stream.

``/plan`` and ``/trip`` persist a run, enqueue a Celery task BY NAME (so the API never
imports the worker/agent stack), and return a ``run_id`` (202). ``/runs/{id}`` reports
status + result; ``/runs/{id}/stream`` streams the agent trace as SSE while it runs.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
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
from tp_core.metrics import record_dispatch, record_rate_limit, render
from tp_core.ratelimit import WINDOW_DAY, WINDOW_MINUTE, allow_request, client_ip
from tp_core.runs import RunRecord, RunStatus, create_run, delete_tenant_data, get_run
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

# Ops endpoints are polled every few seconds (Prometheus scrape, container healthcheck).
# Tracing them floods the trace store -- they were ~94% of all spans -- and buries the
# real agent runs. Excluded here rather than via a compose env var so every deployment
# inherits it: compose, kind/Helm, and local.
_EXCLUDED_URLS = "health,metrics,docs,redoc,openapi.json,favicon.ico"

with suppress(Exception):  # auto request spans; best-effort so a bad agent never blocks boot
    FastAPIInstrumentor.instrument_app(app, excluded_urls=_EXCLUDED_URLS)

_TERMINAL = {RunStatus.succeeded.value, RunStatus.failed.value}


class RunAccepted(BaseModel):
    run_id: str
    status: str = "queued"


class DeletionReceipt(BaseModel):
    tenant_id: str
    runs_deleted: int


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


async def _enforce_rate_limit(endpoint: str, tenant_id: str, request: Request) -> None:
    """429 when any scope is over budget (fail-open if Redis is down).

    THREE checks, strictest wins. A per-tenant limit alone is defeated by rotating the
    session cookie, so the per-IP scope closes that; a per-minute limit alone bounds
    burst but not a caller who sits just under it all day, so the daily window is the
    real budget. Each ships at 0 (disabled), so behaviour is unchanged until set.
    """
    cfg = get_settings()
    ip = client_ip(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else None,
        cfg.trusted_proxy_hops,
    )
    checks: list[tuple[str, str | None, int, int]] = [
        ("tenant_min", tenant_id, cfg.rate_limit_per_min, WINDOW_MINUTE),
        ("tenant_day", tenant_id, cfg.rate_limit_per_day, WINDOW_DAY),
        ("ip_min", ip, cfg.rate_limit_ip_per_min, WINDOW_MINUTE),
    ]
    for scope, identity, limit, window in checks:
        if not identity or limit <= 0:
            continue
        if not await allow_request(identity, limit=limit, window_s=window, scope=scope):
            record_rate_limit(scope, "refused")
            record_dispatch(endpoint, "rate_limited")
            raise HTTPException(status_code=429, detail=f"rate limit exceeded ({scope})")
        record_rate_limit(scope, "allowed")


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
    request: PlanRequest,
    request_ctx: Request,
    principal: Annotated[Principal, Depends(get_principal)],
) -> RunAccepted:
    if not await planning_enabled():
        record_dispatch("plan", "disabled")
        raise HTTPException(status_code=503, detail="planning is temporarily disabled")
    await _enforce_rate_limit("plan", principal.tenant_id, request_ctx)
    run_id = await create_run("plan", request, tenant_id=principal.tenant_id)
    celery_app.send_task("tp_worker.tasks.plan_task", args=[run_id])
    record_dispatch("plan", "queued")
    return RunAccepted(run_id=run_id)


@app.post("/trip", response_model=RunAccepted, status_code=202)
async def create_trip(
    request: TripRequest,
    request_ctx: Request,
    principal: Annotated[Principal, Depends(get_principal)],
) -> RunAccepted:
    if not await planning_enabled():
        record_dispatch("trip", "disabled")
        raise HTTPException(status_code=503, detail="planning is temporarily disabled")
    await _enforce_rate_limit("trip", principal.tenant_id, request_ctx)
    run_id = await create_run("trip", request, tenant_id=principal.tenant_id)
    celery_app.send_task("tp_worker.tasks.trip_task", args=[run_id])
    record_dispatch("trip", "queued")
    return RunAccepted(run_id=run_id)


@app.delete("/me/data", response_model=DeletionReceipt)
async def delete_my_data(
    principal: Annotated[Principal, Depends(get_principal)],
) -> DeletionReceipt:
    """GDPR right-to-be-forgotten: erase every run owned by the caller's tenant.

    Fail-closed — requires a verified principal, and only ever deletes the caller's own
    tenant data (the id comes from the token, never from the request body).
    """
    deleted = await delete_tenant_data(principal.tenant_id)
    record_dispatch("delete_data", "ok")
    return DeletionReceipt(tenant_id=principal.tenant_id, runs_deleted=deleted)


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
