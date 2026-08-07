"""Run progress events over Redis pub/sub.

The worker publishes per-node ``RunEvent``s to channel ``run:{id}`` as the graph
streams; the API's SSE endpoint subscribes and forwards them. Publishing is
BEST-EFFORT: progress is telemetry, never the run — a missing or broken
bus must never fail a job (and, handily, lets the worker unit-tests run with no Redis).
The bus reads ``REDIS_URL`` from the environment, independent of the LLM key.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any, Literal

import redis.asyncio as aioredis
from pydantic import BaseModel

from tp_core.settings import DEFAULT_REDIS_URL

EventType = Literal["node", "done", "failed"]


class RunEvent(BaseModel):
    run_id: str
    type: EventType
    node: str | None = None
    city: str | None = None
    detail: str | None = None


def _channel(run_id: str) -> str:
    return f"run:{run_id}"


def _redis_url() -> str:
    return os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)


@asynccontextmanager
async def run_publisher(run_id: str) -> AsyncIterator[Any]:
    """Yield a best-effort ``emit(event_type, *, node, city, detail)`` bound to ``run_id``."""
    client: Any = None
    with suppress(Exception):  # a down/misconfigured Redis must never fail the run
        client = aioredis.from_url(_redis_url())  # type: ignore[no-untyped-call]  # redis async API

    async def emit(
        event_type: EventType,
        *,
        node: str | None = None,
        city: str | None = None,
        detail: str | None = None,
    ) -> None:
        if client is None:
            return
        with suppress(Exception):  # progress is best-effort — never fail a run on the bus
            event = RunEvent(run_id=run_id, type=event_type, node=node, city=city, detail=detail)
            await client.publish(_channel(run_id), event.model_dump_json())

    try:
        yield emit
    finally:
        if client is not None:
            with suppress(Exception):
                await client.aclose()


async def subscribe(run_id: str) -> AsyncIterator[RunEvent]:
    """Yield live ``RunEvent``s for ``run_id`` until the caller stops iterating."""
    client = aioredis.from_url(_redis_url())  # type: ignore[no-untyped-call]  # redis async API
    pubsub = client.pubsub()
    await pubsub.subscribe(_channel(run_id))
    try:
        async for message in pubsub.listen():
            if message.get("type") == "message":
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                yield RunEvent.model_validate_json(data)
    finally:
        with suppress(Exception):
            await pubsub.unsubscribe(_channel(run_id))
            await pubsub.aclose()
            await client.aclose()
