"""LangGraph checkpointer factory.

Picks a saver by ``DATABASE_URL`` scheme — AsyncSqliteSaver for sqlite (local + tests),
AsyncPostgresSaver for Postgres (prod) — mirroring the run-store's cross-db approach.
When ``run_id`` is None (eval / sync path) it yields ``None`` so the graph compiles
WITHOUT a checkpointer: no persistence, no resume, no extra I/O.

Concurrency note: each call opens its own saver/connection, so the multi-city
coordinator's parallel per-city checkpoints are safe on Postgres. On local sqlite,
heavy concurrent checkpoint writes can hit file-lock contention — a dev-only caveat;
Postgres is the real backend.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from tp_core.settings import DEFAULT_DATABASE_URL


def _sqlite_path(url: str) -> str:
    tail = url.split(":///", 1)[-1] if ":///" in url else url.rsplit("://", 1)[-1]
    return tail or ":memory:"


def _pg_dsn(url: str) -> str:
    # psycopg DSN — drop any SQLAlchemy async-driver suffix
    return url.replace("+asyncpg", "").replace("+psycopg", "")


@asynccontextmanager
async def make_checkpointer(run_id: str | None) -> AsyncIterator[Any]:
    """Yield a LangGraph checkpointer for ``run_id``, or ``None`` to skip checkpointing."""
    if run_id is None:
        yield None
        return
    url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    if url.startswith("sqlite"):
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        async with AsyncSqliteSaver.from_conn_string(_sqlite_path(url)) as saver:
            await saver.setup()
            yield saver
    else:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(_pg_dsn(url)) as saver:
            await saver.setup()
            yield saver
