"""/plan + /trip dispatch async runs; /runs/{id} status; /runs/{id}/stream SSE.

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


def _capture_run_ids(monkeypatch) -> list[str]:
    """Record the id create_run hands out - a 503 has no body to carry it."""
    ids: list[str] = []
    real_create = main.create_run

    async def _capture(*args, **kwargs):
        run_id = await real_create(*args, **kwargs)
        ids.append(run_id)
        return run_id

    monkeypatch.setattr(main, "create_run", _capture)
    return ids


def test_dispatch_failure_answers_503_and_fails_the_run(monkeypatch):
    """A dead broker must not strand the run at `queued`.

    It used to: the row was written, send_task raised, the caller got a 500 - and the
    database kept promising a run that would never start. Found live when Redis was
    stopped during `make infra-drill`: three rows stuck at `queued` indefinitely.
    """
    from tp_core.runs import get_run

    def _broker_down(*args, **kwargs):
        raise ConnectionError("Error 111 connecting to redis:6379. Connection refused.")

    ids = _capture_run_ids(monkeypatch)
    monkeypatch.setattr(core_celery.celery_app, "send_task", _broker_down)
    resp = client.post("/plan", json={"city": "Tokyo", "interests": ["temples"]})
    assert resp.status_code == 503
    assert "queue" in resp.json()["detail"]

    record = asyncio.run(get_run(ids[0]))
    assert record is not None
    assert record.status == "failed"
    assert "dispatch failed" in (record.error or "")


def test_hung_broker_is_cut_off_not_waited_on(monkeypatch):
    """A broker that HANGS (vs refuses) must still get a prompt 503, not a stuck request.

    Timed INSIDE the coroutine, on a loop this test owns. Timing a TestClient call
    measures the harness instead: each un-contexted request tears its loop down, and
    that teardown waits for the still-sleeping send_task thread. A long-lived server
    loop never waits for it - which is exactly the property being tested.
    """
    import time

    import pytest
    from fastapi import HTTPException

    failed: list[str] = []

    async def _mark_failed(run_id: str, error: str) -> None:
        failed.append(run_id)

    monkeypatch.setattr(main, "_DISPATCH_TIMEOUT_S", 0.1)
    monkeypatch.setattr(main, "mark_failed", _mark_failed)
    monkeypatch.setattr(core_celery.celery_app, "send_task", lambda *a, **k: time.sleep(1.0))

    async def _timed() -> float:
        started = time.monotonic()
        with pytest.raises(HTTPException) as exc:
            await main._dispatch("trip", "tp_worker.tasks.trip_task", "run-123")
        assert exc.value.status_code == 503
        return time.monotonic() - started

    loop = asyncio.new_event_loop()
    try:
        elapsed = loop.run_until_complete(_timed())
    finally:
        loop.close()  # no shutdown_default_executor(): do not wait for the hung thread
    assert elapsed < 0.6  # answered at the timeout, not after the hang
    assert failed == ["run-123"]  # and the run was compensated


def test_unknown_run_404():
    assert client.get("/runs/does-not-exist").status_code == 404


def test_plan_validation_error():
    assert client.post("/plan", json={"city": "Tokyo"}).status_code == 422


def test_request_size_is_bounded(monkeypatch):
    """Nothing capped these before: a 50KB `interest` went straight into the LLM prompt."""
    monkeypatch.setattr(core_celery.celery_app, "send_task", lambda *a, **k: None)
    ok = {"city": "Kyoto", "interests": ["temples"]}
    assert client.post("/plan", json=ok).status_code == 202

    too_long_city = {**ok, "city": "K" * 121}
    too_long_interest = {**ok, "interests": ["x" * 81]}
    too_many_interests = {**ok, "interests": [f"i{n}" for n in range(13)]}
    for body in (too_long_city, too_long_interest, too_many_interests):
        assert client.post("/plan", json=body).status_code == 422

    trip_long_city = {"cities": ["Kyoto", "O" * 121], "interests": ["food"]}
    assert client.post("/trip", json=trip_long_city).status_code == 422


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


# --- a dead database is a 503 that says so, never a bare 500 (2026-10-01) ------------------

def test_database_down_is_a_503_that_names_the_database(monkeypatch):
    """Postgres unreachable was a bare 500 (infra drill Q16). Still fail-CLOSED - no run id
    is handed out - but now a retryable 503 the UI can word as an outage, not a switch."""

    async def refused(*args, **kwargs):
        raise OSError(111, "Connect call failed ('db', 5432)")

    monkeypatch.setattr(main, "create_run", refused)
    for path, body in (
        ("/plan", {"city": "Kyoto", "interests": ["food"], "days": 1}),
        ("/trip", {"cities": ["Kyoto", "Osaka"], "interests": ["food"], "days": 2}),
    ):
        resp = client.post(path, json=body)
        assert resp.status_code == 503, path
        assert "database" in resp.json()["detail"]
        assert "disabled" not in resp.json()["detail"]  # that wording is the kill switch's


def test_an_open_postgres_breaker_is_a_503_too(monkeypatch):
    """After 3 failures session_scope refuses by itself - same answer, sooner."""
    from sqlalchemy.exc import OperationalError

    async def breaker_open(*args, **kwargs):
        raise OperationalError("postgres circuit is OPEN", None, Exception("circuit open"))

    monkeypatch.setattr(main, "get_run", breaker_open)
    resp = client.get("/runs/any-run")
    assert resp.status_code == 503
    assert "database" in resp.json()["detail"]


def test_a_bug_is_still_a_500_not_dressed_up_as_an_outage(monkeypatch):
    """Only an UNREACHABLE database maps to 503 - a real bug must stay a visible 500."""

    async def bug(*args, **kwargs):
        raise ValueError("a real bug, not an outage")

    monkeypatch.setattr(main, "create_run", bug)
    unsafe = TestClient(app, raise_server_exceptions=False)
    resp = unsafe.post("/plan", json={"city": "Kyoto", "interests": ["food"], "days": 1})
    assert resp.status_code == 500


def test_metrics_carry_todays_spend_from_the_breaker_ledger(monkeypatch):
    """Grafana's "Spend today" reads this: the Redis day total, not a per-process counter."""

    async def today() -> float:
        return 0.00547

    monkeypatch.setattr(main, "spend_today", today)
    assert "tp_spend_today_usd 0.00547" in client.get("/metrics").text
