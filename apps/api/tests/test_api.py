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


def test_metrics_endpoint_exposes_prometheus_text():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    # An unlabeled counter always emits a sample line (labeled ones only after first use).
    assert "tp_critic_revisions_total" in resp.text


def _enable_auth(monkeypatch):
    from tp_core.settings import get_settings

    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH0_DOMAIN", "tp.us.auth0.com")
    monkeypatch.setenv("AUTH0_AUDIENCE", "tp-api")
    get_settings.cache_clear()


def test_plan_rejects_missing_token_when_auth_enabled(monkeypatch):
    _enable_auth(monkeypatch)
    resp = client.post("/plan", json={"city": "Tokyo", "interests": ["temples"]})
    assert resp.status_code == 401


def test_plan_accepts_valid_token_when_auth_enabled(monkeypatch):
    from tp_core.auth import Principal

    _enable_auth(monkeypatch)
    principal = Principal(sub="u", tenant_id="acme")
    monkeypatch.setattr(main, "verify_token", lambda token, **k: principal)
    monkeypatch.setattr(core_celery.celery_app, "send_task", lambda *a, **k: None)
    resp = client.post(
        "/plan",
        json={"city": "Tokyo", "interests": ["temples"]},
        headers={"Authorization": "Bearer good-token"},
    )
    assert resp.status_code == 202


def test_health_and_metrics_stay_open_under_auth(monkeypatch):
    _enable_auth(monkeypatch)
    assert client.get("/health").status_code == 200
    assert client.get("/metrics").status_code == 200


def test_plan_rate_limited_returns_429(monkeypatch):
    async def _deny(*args, **kwargs):
        return False

    monkeypatch.setattr(main, "allow_request", _deny)
    monkeypatch.setattr(core_celery.celery_app, "send_task", lambda *a, **k: None)
    resp = client.post("/plan", json={"city": "Tokyo", "interests": ["temples"]})
    assert resp.status_code == 429


def test_runs_are_tenant_isolated(monkeypatch):
    from tp_core.auth import Principal

    _enable_auth(monkeypatch)
    # The bearer token's value doubles as the tenant id for the test.
    def _as_tenant(token, **k):
        return Principal(sub=token, tenant_id=token)

    monkeypatch.setattr(main, "verify_token", _as_tenant)
    monkeypatch.setattr(core_celery.celery_app, "send_task", lambda *a, **k: None)

    created = client.post(
        "/plan",
        json={"city": "Tokyo", "interests": ["temples"]},
        headers={"Authorization": "Bearer acme"},
    )
    run_id = created.json()["run_id"]

    other = client.get(f"/runs/{run_id}", headers={"Authorization": "Bearer globex"})
    assert other.status_code == 404  # another tenant can't even tell it exists
    owner = client.get(f"/runs/{run_id}", headers={"Authorization": "Bearer acme"})
    assert owner.status_code == 200


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
        # tenant "local" matches LOCAL_PRINCIPAL (auth is off in tests by default).
        rid = await create_run(
            "plan", PlanRequest(city="Tokyo", interests=["temples"]), tenant_id="local"
        )
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


def test_delete_my_data_erases_callers_runs(monkeypatch):
    monkeypatch.setattr(core_celery.celery_app, "send_task", lambda *a, **k: None)
    run_id = client.post("/plan", json={"city": "Tokyo", "interests": ["temples"]}).json()["run_id"]
    assert client.get(f"/runs/{run_id}").status_code == 200

    resp = client.request("DELETE", "/me/data")
    assert resp.status_code == 200
    assert resp.json()["runs_deleted"] >= 1
    assert client.get(f"/runs/{run_id}").status_code == 404  # erased


def test_delete_my_data_is_tenant_scoped(monkeypatch):
    from tp_core.auth import Principal

    _enable_auth(monkeypatch)

    def _as_tenant(token, **k):
        return Principal(sub=token, tenant_id=token)

    monkeypatch.setattr(main, "verify_token", _as_tenant)
    monkeypatch.setattr(core_celery.celery_app, "send_task", lambda *a, **k: None)

    acme = client.post(
        "/plan", json={"city": "Tokyo", "interests": ["temples"]},
        headers={"Authorization": "Bearer acme"},
    ).json()["run_id"]
    globex = client.post(
        "/plan", json={"city": "Osaka", "interests": ["food"]},
        headers={"Authorization": "Bearer globex"},
    ).json()["run_id"]

    client.request("DELETE", "/me/data", headers={"Authorization": "Bearer acme"})

    # acme's run is gone; globex's is untouched (no cross-tenant deletion).
    acme_hdr = {"Authorization": "Bearer acme"}
    globex_hdr = {"Authorization": "Bearer globex"}
    assert client.get(f"/runs/{acme}", headers=acme_hdr).status_code == 404
    assert client.get(f"/runs/{globex}", headers=globex_hdr).status_code == 200


def test_plan_blocked_when_kill_switch_off(monkeypatch):
    async def disabled():
        return False

    monkeypatch.setattr(main, "planning_enabled", disabled)
    resp = client.post("/plan", json={"city": "Tokyo", "interests": ["temples"]})
    assert resp.status_code == 503
