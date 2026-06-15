"""Postgres-backed run-state store (S9, Decision 1).

A *run* is the durable record of one planning request: status, the request, the
final result (or error), accumulated warnings, and cost. Distinct from the LangGraph
checkpointer (S9b) which persists *in-run* graph state — this table is the
business-level run lifecycle the API reports on and the worker updates.

JSON columns use ``JSONB`` on Postgres and plain ``JSON`` on SQLite (tests), so the
same code runs against hermetic file-SQLite locally and Aurora in production.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, Float, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from tp_core.db import Base, session_scope

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
    tenant_id: Mapped[str | None] = mapped_column(String(36), default=None, index=True)  # S12
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


async def mark_failed(run_id: str, error: str) -> None:
    await _update(run_id, status=RunStatus.failed.value, error=error)
