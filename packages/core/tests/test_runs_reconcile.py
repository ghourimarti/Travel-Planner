"""Orphan reconciliation: close runs whose task was lost - only when nothing is in flight."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from prometheus_client import REGISTRY
from pydantic import BaseModel
from tp_core import runs
from tp_core.db import session_scope


class _Req(BaseModel):
    city: str = "Kyoto"


async def _age(run_id: str, minutes: int) -> None:
    async with session_scope() as session:
        run = await session.get(runs.Run, run_id)
        assert run is not None
        run.updated_at = datetime.now(UTC) - timedelta(minutes=minutes)


async def _idle() -> bool:
    return True


async def _busy() -> bool:
    return False


def _orphans_counted() -> float:
    return REGISTRY.get_sample_value("tp_errors_total", {"type": "orphaned_run"}) or 0.0


def test_closes_only_old_open_runs_when_nothing_is_in_flight(db) -> None:  # noqa: ANN001
    before = _orphans_counted()

    async def go() -> tuple[list[str], list[str], list[runs.RunRecord | None]]:
        old_queued = await runs.create_run("plan", _Req())
        await _age(old_queued, 20)
        old_running = await runs.create_run("plan", _Req())
        await runs.mark_running(old_running)
        await _age(old_running, 20)
        fresh = await runs.create_run("plan", _Req())
        finished = await runs.create_run("plan", _Req())
        await runs.mark_failed(finished, "a real failure")
        await _age(finished, 20)
        ids = [old_queued, old_running, fresh, finished]
        closed = await runs.reconcile_orphans(in_flight_check=_idle)
        return ids, closed, [await runs.get_run(i) for i in ids]

    ids, closed, recs = asyncio.run(go())
    assert sorted(closed) == sorted(ids[:2])
    assert [r.status for r in recs if r] == ["failed", "failed", "queued", "failed"]
    assert recs[0] and (recs[0].error or "").startswith("orphaned: stuck 'queued'")
    assert recs[1] and (recs[1].error or "").startswith("orphaned: stuck 'running'")
    assert recs[3] and recs[3].error == "a real failure"  # a finished run is never touched
    assert _orphans_counted() == before + 2


def test_does_nothing_while_anything_is_in_flight(db) -> None:  # noqa: ANN001
    """A run merely waiting behind a long queue must never be closed."""

    async def go() -> tuple[list[str], runs.RunRecord | None]:
        waiting = await runs.create_run("plan", _Req())
        await _age(waiting, 60)
        closed = await runs.reconcile_orphans(in_flight_check=_busy)
        return closed, await runs.get_run(waiting)

    closed, rec = asyncio.run(go())
    assert closed == []
    assert rec is not None and rec.status == "queued"


def test_an_unreadable_broker_counts_as_busy(monkeypatch) -> None:  # noqa: ANN001
    """If Redis cannot say what is in flight, the reconciler must not guess."""

    def down(*_: object, **__: object) -> object:
        raise ConnectionError("redis down")

    monkeypatch.setattr(runs.aioredis, "from_url", down)
    assert asyncio.run(runs._nothing_in_flight()) is False
