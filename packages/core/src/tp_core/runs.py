"""Postgres-backed run-state store.

A *run* is the durable record of one planning request: status, the request, the
final result (or error), accumulated warnings, and cost. Distinct from the LangGraph
checkpointer, which persists *in-run* graph state — this table is the
business-level run lifecycle the API reports on and the worker updates.

JSON columns use ``JSONB`` on Postgres and plain ``JSON`` on SQLite (tests), so the
same code runs against hermetic file-SQLite locally and Aurora in production.
"""

from __future__ import annotations

import enum
import os
import uuid
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any, cast

import redis.asyncio as aioredis
from pydantic import BaseModel, Field
from sqlalchemy import JSON, CursorResult, DateTime, Float, String, delete, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tp_core.db import Base, session_scope
from tp_core.metrics import record_error
from tp_core.settings import DEFAULT_REDIS_URL

_JSON = JSON().with_variant(JSONB, "postgresql")  # JSONB on Postgres, JSON on SQLite


class RunStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class Run(Base):
    """ORM row for one planning run."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # "plan" | "trip"
    status: Mapped[str] = mapped_column(String(16), default=RunStatus.queued.value, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)
    request: Mapped[dict[str, Any]] = mapped_column(_JSON)
    result: Mapped[dict[str, Any] | None] = mapped_column(_JSON, default=None)
    error: Mapped[str | None] = mapped_column(String, default=None)
    warnings: Mapped[list[str]] = mapped_column(_JSON, default=list)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RunRecord(BaseModel):
    """API read-model for a run (serialized by FastAPI)."""

    model_config = {"from_attributes": True}

    id: str
    kind: str
    status: str
    # Internal: the worker scopes retrieval by it, but it's never serialized to the API.
    tenant_id: str | None = Field(default=None, exclude=True)
    request: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    warnings: list[str] = []
    cost_usd: float = 0.0
    created_at: datetime | None = None
    updated_at: datetime | None = None


async def create_run(kind: str, request: BaseModel, *, tenant_id: str | None = None) -> str:
    """Persist a queued run and return its id."""
    run_id = str(uuid.uuid4())
    async with session_scope() as session:
        session.add(
            Run(
                id=run_id,
                kind=kind,
                status=RunStatus.queued.value,
                tenant_id=tenant_id,
                request=request.model_dump(mode="json"),
            )
        )
    return run_id


async def get_run(run_id: str, *, tenant_id: str | None = None) -> RunRecord | None:
    """Return the run record, or ``None`` if it doesn't exist.

    When ``tenant_id`` is given (API reads), a run owned by a different tenant is
    treated as absent — a cross-tenant id is indistinguishable from an unknown one, so
    ownership can't be probed. The worker calls this unscoped (it owns the lifecycle).
    """
    async with session_scope() as session:
        run = await session.get(Run, run_id)
        if run is None or (tenant_id is not None and run.tenant_id != tenant_id):
            return None
        return RunRecord.model_validate(run)


async def delete_tenant_data(tenant_id: str) -> int:
    """Erase every run owned by a tenant — the GDPR right-to-be-forgotten path.

    Returns the number of rows deleted. Tenant-scoped by construction: a caller can
    only ever pass their own ``tenant_id`` (the API derives it from the verified token),
    so there's no cross-tenant deletion path.
    """
    async with session_scope() as session:
        result = await session.execute(delete(Run).where(Run.tenant_id == tenant_id))
        return cast("CursorResult[Any]", result).rowcount or 0


async def _update(run_id: str, **fields: Any) -> None:
    async with session_scope() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        for key, value in fields.items():
            setattr(run, key, value)


async def mark_running(run_id: str) -> None:
    await _update(run_id, status=RunStatus.running.value)


async def mark_succeeded(
    run_id: str, result: BaseModel, *, cost_usd: float, warnings: list[str]
) -> None:
    await _update(
        run_id,
        status=RunStatus.succeeded.value,
        result=result.model_dump(mode="json"),
        cost_usd=cost_usd,
        warnings=warnings,
    )


async def mark_failed(run_id: str, error: str, *, cost_usd: float = 0.0) -> None:
    """Close a run as failed, keeping what it SPENT first - a failed run is not a free
    one (the worker passes its tally: tp_core.control.track_run_spend)."""
    await _update(run_id, status=RunStatus.failed.value, error=error, cost_usd=cost_usd)


# --- orphan reconciliation ----------------------------------------------------------
#
# A run row is written before its task runs, and only a task ever closes it. If the task
# is lost - or dies before it can reach Postgres (4 runs were stranded that way under
# load, 2026-09-30) - the row stays `queued`/`running` and anyone polling it waits forever.

ORPHAN_AFTER_S = 900.0  # 15 min: well past the Celery visibility timeout (360 s) + a run
_OPEN = (RunStatus.queued.value, RunStatus.running.value)
_QUEUE = "celery"
# kombu's Redis transport keeps priority messages in `<queue>\x06\x16<step>` lists.
_QUEUE_KEYS = (_QUEUE, *(f"{_QUEUE}\x06\x16{step}" for step in (3, 6, 9)))


async def _nothing_in_flight() -> bool:
    """True only when NO task is queued or unacknowledged (being worked on) anywhere.

    If Redis cannot say, the answer is False: a reconciler that guesses would close runs
    a worker is about to pick up.
    """
    client: Any = None
    try:
        client = aioredis.from_url(  # type: ignore[no-untyped-call]
            os.environ.get("REDIS_URL", DEFAULT_REDIS_URL), socket_connect_timeout=0.5
        )
        for key in _QUEUE_KEYS:
            if int(await client.llen(key)):
                return False
        return int(await client.hlen("unacked")) == 0
    except Exception:
        return False
    finally:
        if client is not None:
            with suppress(Exception):
                await client.aclose()


async def reconcile_orphans(
    *,
    older_than_s: float = ORPHAN_AFTER_S,
    in_flight_check: Callable[[], Awaitable[bool]] = _nothing_in_flight,
) -> list[str]:
    """Close runs that can never finish; return their ids.

    Acts only when nothing is in flight, so a run merely waiting behind a long queue is
    never touched - it is closed only once the queue is empty and it is STILL open,
    ``older_than_s`` after its last update. Each close is counted as
    ``tp_errors_total{type="orphaned_run"}``: an orphan is a lost task, not a user error.
    """
    if not await in_flight_check():
        return []
    now = datetime.now(UTC)
    closed: list[str] = []
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(Run).where(Run.status.in_(_OPEN)).with_for_update(skip_locked=True)
            )
        ).scalars()
        for run in rows:
            touched = run.updated_at or run.created_at
            if touched is None:
                continue
            if touched.tzinfo is None:  # SQLite (tests) stores naive UTC
                touched = touched.replace(tzinfo=UTC)
            if (now - touched).total_seconds() < older_than_s:
                continue
            previous = run.status
            run.status = RunStatus.failed.value
            run.error = (
                f"orphaned: stuck '{previous}' with nothing in flight for "
                f"{int(older_than_s // 60)}+ min - its task was lost"
            )
            closed.append(run.id)
    for _ in closed:
        record_error("orphaned_run")
    return closed
