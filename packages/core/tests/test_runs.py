"""S9a: the run-state store, exercised on hermetic file-SQLite (the ``db`` fixture)."""

from __future__ import annotations

import asyncio

from pydantic import BaseModel
from tp_core.runs import (
    RunStatus,
    create_run,
    get_run,
    mark_failed,
    mark_running,
    mark_succeeded,
)


class _Req(BaseModel):
    city: str
    interests: list[str]


class _Res(BaseModel):
    summary_markdown: str
    cost_usd: float = 0.0
    warnings: list[str] = []


def test_create_get_roundtrip(db):
    async def go():
        run_id = await create_run("plan", _Req(city="Tokyo", interests=["temples"]))
        rec = await get_run(run_id)
        assert rec is not None
        assert rec.kind == "plan"
        assert rec.status == RunStatus.queued.value
        assert rec.request == {"city": "Tokyo", "interests": ["temples"]}

    asyncio.run(go())


def test_status_transitions(db):
    async def go():
        run_id = await create_run("plan", _Req(city="Osaka", interests=["food"]))
        await mark_running(run_id)
        running = await get_run(run_id)
        assert running is not None and running.status == RunStatus.running.value
        await mark_succeeded(
            run_id,
            _Res(summary_markdown="ok", cost_usd=0.02, warnings=["w"]),
            cost_usd=0.02,
            warnings=["w"],
        )
        rec = await get_run(run_id)
        assert rec is not None
        assert rec.status == RunStatus.succeeded.value
        assert rec.result is not None and rec.result["summary_markdown"] == "ok"
        assert rec.cost_usd == 0.02
        assert rec.warnings == ["w"]

    asyncio.run(go())


def test_mark_failed(db):
    async def go():
        run_id = await create_run("trip", _Req(city="X", interests=["y"]))
        await mark_failed(run_id, "boom")
        rec = await get_run(run_id)
        assert rec is not None
        assert rec.status == RunStatus.failed.value
        assert rec.error == "boom"

    asyncio.run(go())


def test_missing_returns_none(db):
    assert asyncio.run(get_run("nope")) is None


def test_tenant_scoped_reads(db):
    async def go():
        run_id = await create_run(
            "plan", _Req(city="Tokyo", interests=["temples"]), tenant_id="acme"
        )
        # Owner sees it; another tenant gets None (404 upstream); unscoped (worker) sees it.
        assert (await get_run(run_id, tenant_id="acme")) is not None
        assert (await get_run(run_id, tenant_id="globex")) is None
        assert (await get_run(run_id)) is not None

    asyncio.run(go())
