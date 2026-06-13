"""S4: the /plan endpoint wraps the planner; /health is dependency-free.

``plan`` is monkeypatched so the endpoint test needs no tools/LLM/key.
"""

from __future__ import annotations

import pytest
import tp_api.main as main
from fastapi.testclient import TestClient
from tp_agents import Itinerary, PlanRequest
from tp_api.main import app

client = TestClient(app)


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_plan_returns_itinerary(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_plan(request: PlanRequest) -> Itinerary:
        return Itinerary(city=request.city, summary_markdown="ok", grounded=True)

    monkeypatch.setattr(main, "plan", fake_plan)
    resp = client.post("/plan", json={"city": "Tokyo", "interests": ["temples"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["city"] == "Tokyo"
    assert body["grounded"] is True


def test_plan_validation_error() -> None:
    resp = client.post("/plan", json={"city": "Tokyo"})  # missing required interests
    assert resp.status_code == 422
