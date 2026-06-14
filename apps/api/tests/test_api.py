"""S9a: /plan + /trip dispatch async runs; /runs/{id} reports status.

Celery dispatch is mocked (no broker); the DB is throwaway file-SQLite (conftest).
"""

from __future__ import annotations

import tp_core.celery as core_celery
from fastapi.testclient import TestClient
from tp_api.main import app

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
