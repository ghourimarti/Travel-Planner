"""S9a/S9c: /plan + /trip dispatch async runs; /runs/{id} status; /runs/{id}/stream SSE.

Celery dispatch and the event subscriber are mocked; the DB is throwaway file-SQLite.
"""

from __future__ import annotations

import asyncio

import tp_api.main as main
import tp_core.celery as core_celery
from fastapi.testclient import TestClient
from tp_agents import Itinerary, PlanRequest
from tp_api.main import app
from tp_core.events import RunEvent
from tp_core.runs import create_run, mark_succeeded

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_plan_dispatches_and_returns_run_id(monkeypatch):
    sent = []
    monkeypatch.setattr(
        core_celery.celery_app, "send_task", lambda name, args=None, **k: sent.append((name, args))
    )
    resp = client.post("/plan", json={"city": "Tokyo", "interests": ["temples"]})
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]
    assert sent == [("tp_worker.tasks.plan_task", [run_id])]

    status = client.get(f"/runs/{run_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "queued"
    assert body["kind"] == "plan"


def test_trip_dispatches(monkeypatch):
    monkeypatch.setattr(core_celery.celery_app, "send_task", lambda *a, **k: None)
    resp = client.post("/trip", json={"cities": ["Tokyo", "Osaka"], "interests": ["food"]})
    assert resp.status_code == 202


def test_unknown_run_404():
    assert client.get("/runs/does-not-exist").status_code == 404


def test_plan_validation_error():
    assert client.post("/plan", json={"city": "Tokyo"}).status_code == 422


def test_stream_forwards_live_events(monkeypatch):
    monkeypatch.setattr(core_celery.celery_app, "send_task", lambda *a, **k: None)
    run_id = client.post("/plan", json={"city": "Tokyo", "interests": ["temples"]}).json()["run_id"]

    async def fake_subscribe(rid):
        yield RunEvent(run_id=rid, type="node", node="geocode")
        yield RunEvent(run_id=rid, type="done")

    monkeypatch.setattr(main, "subscribe", fake_subscribe)
    with client.stream("GET", f"/runs/{run_id}/stream") as resp:
        body = "".join(resp.iter_text())
    assert '"status": "queued"' in body
    assert '"node": "geocode"' in body
    assert '"type": "done"' in body


def test_stream_terminal_run_short_circuits(monkeypatch):
    async def seed():
        rid = await create_run("plan", PlanRequest(city="Tokyo", interests=["temples"]))
        await mark_succeeded(
            rid,
            Itinerary(city="Tokyo", summary_markdown="ok", grounded=True),
            cost_usd=0.01,
            warnings=[],
        )
        return rid

    run_id = asyncio.run(seed())

    def must_not_subscribe(rid):
        raise AssertionError("a terminal run must not subscribe to the bus")

    monkeypatch.setattr(main, "subscribe", must_not_subscribe)
    with client.stream("GET", f"/runs/{run_id}/stream") as resp:
        body = "".join(resp.iter_text())
    assert '"type": "succeeded"' in body
