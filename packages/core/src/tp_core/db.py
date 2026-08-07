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

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from tp_core.settings import DEFAULT_DATABASE_URL


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


def _make_engine() -> AsyncEngine:
    url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    return create_async_engine(url, poolclass=NullPool, future=True)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Yield a session in a transaction; commit on success, roll back on error."""
    engine = _make_engine()
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
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
