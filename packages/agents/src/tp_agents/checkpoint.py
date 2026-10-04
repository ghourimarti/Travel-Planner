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

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from tp_core.settings import DEFAULT_DATABASE_URL

#: Every project type that may be deserialized from a checkpoint. LangGraph's default
#: serializer allowed ANY type with a warning - "Deserializing unregistered type ...
#: This will be blocked in a future version" - logged on every resumed run. An upgrade
#: that flips that default would have broken resume with no code change on our side.
#:
#: Passing a list switches the serializer to STRICT: built-in safe types plus these,
#: anything else BLOCKED. So the list is deliberately complete, not just the six types
#: the warning happened to name - nested DayPlan/ItineraryItem and the trip models are
#: here too, because a missing entry fails a resume, while an extra one costs nothing.
STATE_TYPES: tuple[tuple[str, str], ...] = (
    *(
        ("tp_agents.schemas", name)
        for name in (
            "PlanRequest", "ItineraryItem", "DayPlan", "Itinerary",
            "CriticVerdict", "TripRequest", "TripItinerary",
        )
    ),
    *(("tp_tools.models", name) for name in ("GeoLocation", "POI", "WeatherDaily", "RouteLeg")),
)


def state_serde() -> JsonPlusSerializer:
    """The checkpoint serializer, with project types explicitly allowed."""
    return JsonPlusSerializer(allowed_msgpack_modules=STATE_TYPES)


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
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        # Constructed directly because AsyncSqliteSaver.from_conn_string takes no `serde`;
        # this is exactly what that helper does, plus the serializer.
        async with aiosqlite.connect(_sqlite_path(url)) as conn:
            saver = AsyncSqliteSaver(conn, serde=state_serde())
            await saver.setup()
            yield saver
    else:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(
            _pg_dsn(url), serde=state_serde()
        ) as pg_saver:
            await pg_saver.setup()
            yield pg_saver
