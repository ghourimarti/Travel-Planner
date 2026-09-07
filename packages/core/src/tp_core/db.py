"""Async SQLAlchemy engine + transactional session + schema init.

The DB URL is read from the environment independently of the LLM settings, so the
API/worker can stand up persistence WITHOUT a provider key (the run-state store and
the planner key are unrelated concerns). A fresh ``NullPool`` engine is created per
``session_scope`` and disposed at the end: this is bullet-proof across the worker's
per-task ``asyncio.run`` loops — no connection is ever shared between event loops.
Connection pooling is a throughput optimization to revisit under sustained load, not
a correctness need at this scale.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from tp_core.llm.circuit import infra_breaker
from tp_core.metrics import record_error
from tp_core.settings import DEFAULT_DATABASE_URL


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


def _make_engine() -> AsyncEngine:
    url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    return create_async_engine(url, poolclass=NullPool, future=True)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Yield a session in a transaction; commit on success, roll back on error.

    BREAKER-GUARDED, AND DELIBERATELY NOT A DEGRADE PATH
    ----------------------------------------------------
    Every persistence call funnels through here, and the engine uses ``NullPool`` — a
    fresh connection per call. So a dead Postgres does not fail cheaply: every request
    pays a full connect timeout before erroring, and a slow database becomes a slow
    APPLICATION. The breaker converts that from a per-request cost into one probe per
    cooldown.

    What it deliberately does NOT do is swallow the failure. It would be easy to
    "degrade gracefully" here by returning without persisting, and that would be far
    worse than the error it replaces: `create_run` would hand back a run id that does
    not exist, and `mark_succeeded` would drop a finished itinerary on the floor. A
    caller cannot tell those apart from success. So an open breaker RAISES — the same
    class of failure the caller already handles, just sooner and without the pileup.

    The cost of this trade is honest: a brief outage can be extended by up to one
    cooldown, because the breaker keeps refusing for `POSTGRES_CIRCUIT_COOLDOWN_SECONDS`
    after the database recovers. Three CONSECUTIVE failures are required to open it, so
    a single blip does not.
    """
    breaker = infra_breaker("postgres")
    if not breaker.allows("postgres"):
        record_error("postgres_circuit_open")
        raise OperationalError(
            "postgres circuit is OPEN: refusing to attempt a connection. "
            "Three consecutive failures were seen; one probe is admitted per cooldown.",
            None,
            Exception("circuit open"),
        )

    engine = _make_engine()
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            try:
                yield session
                await session.commit()
                breaker.record_success("postgres")
            except Exception:
                await session.rollback()
                raise
    except Exception:
        # Counts against the breaker whether the fault was connectivity or a bad
        # statement. Distinguishing them here would need driver-specific error
        # classification, and being wrong in the lenient direction means the breaker
        # never opens on the outage it exists for.
        breaker.record_failure("postgres")
        record_error("postgres_error")
        raise
    finally:
        await engine.dispose()


async def init_models() -> None:
    """Create tables if absent (``create_all``; migrate to Alembic once schemas evolve).

    The API and worker both call this on boot and can start simultaneously (e.g.
    ``make bootstrap``). On an empty DB, two concurrent ``create_all`` calls race in
    the pg_catalog and one fails with a UniqueViolation. A transaction-scoped advisory
    lock serializes them: the second caller waits, then ``checkfirst`` finds the tables
    already present and no-ops. The lock auto-releases when the ``begin()`` transaction
    ends. No-op on SQLite (advisory locks are Postgres-only).
    """
    from tp_core import runs  # noqa: F401  -- import so models register on Base.metadata

    engine = _make_engine()
    is_postgres = engine.url.get_backend_name() == "postgresql"
    try:
        async with engine.begin() as conn:
            if is_postgres:
                # Arbitrary fixed key shared by every init_models caller.
                await conn.exec_driver_sql("SELECT pg_advisory_xact_lock(927140251)")
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


async def dispose_engine() -> None:
    """No-op: per-scope engines self-dispose. Kept for API-lifespan symmetry."""
    return None
