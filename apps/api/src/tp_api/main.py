"""FastAPI app exposing the planner.

The gateway and corpus retriever are built lazily (not at import), so this module
imports without an API key. The retriever is a FastAPI dependency so tests can
override it without standing up embeddings/Qdrant.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from tp_agents import Itinerary, PlanRequest, plan
from tp_agents.nodes import PoiRetriever
from tp_retrieval import get_retriever

app = FastAPI(title="AI Travel Planner API", version="0.1.0")


def get_planner_retriever() -> PoiRetriever:
    """Corpus retriever dependency (overridden in tests)."""
    return get_retriever()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/plan", response_model=Itinerary)
async def create_plan(
    request: PlanRequest,
    retriever: Annotated[PoiRetriever, Depends(get_planner_retriever)],
) -> Itinerary:
    # Corpus retrieval is the grounded POI source; the live tool is the fallback.
    return await plan(request, retriever=retriever)
