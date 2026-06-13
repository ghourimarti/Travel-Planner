"""FastAPI app exposing the planner.

The gateway is built lazily inside ``plan`` (not at import), so this module
imports without an API key — TestClient and CI need no secrets to load the app.
"""

from __future__ import annotations

from fastapi import FastAPI
from tp_agents import Itinerary, PlanRequest, plan

app = FastAPI(title="AI Travel Planner API", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/plan", response_model=Itinerary)
async def create_plan(request: PlanRequest) -> Itinerary:
    return await plan(request)
