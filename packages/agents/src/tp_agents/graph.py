"""Assemble the single-agent planner graph: geocode -> gather -> compose.

Deliberately linear for S4 (the walking skeleton). Conditional routing, a critic,
and per-city fan-out arrive in S7/S8. The gateway and the (optional) corpus
retriever are closed over their nodes so they never live in serializable state.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from tp_core.llm import LLMGateway

from tp_agents.nodes import PoiRetriever, compose_node, gather_node, geocode_node
from tp_agents.schemas import Itinerary, PlanRequest
from tp_agents.state import PlannerState


def build_planner_graph(gateway: LLMGateway, retriever: PoiRetriever | None = None) -> Any:
    """Compile the planner graph with ``gateway`` (+ optional ``retriever``) bound."""
    builder = StateGraph(PlannerState)
    builder.add_node("geocode", geocode_node)

    async def gather(state: PlannerState) -> dict[str, Any]:
        return await gather_node(state, retriever=retriever)

    async def compose(state: PlannerState) -> dict[str, Any]:
        return await compose_node(state, gateway)

    builder.add_node("gather", gather)
    builder.add_node("compose", compose)
    builder.add_edge(START, "geocode")
    builder.add_edge("geocode", "gather")
    builder.add_edge("gather", "compose")
    builder.add_edge("compose", END)
    return builder.compile()


async def plan(
    request: PlanRequest,
    *,
    gateway: LLMGateway | None = None,
    retriever: PoiRetriever | None = None,
) -> Itinerary:
    """Run the planner for one request and return the grounded itinerary.

    ``gateway`` and ``retriever`` are injectable for tests; in production the gateway
    is built lazily from settings and the API passes a corpus retriever. With no
    retriever, the planner uses the live POI tool (the S4 behaviour).
    """
    gw = gateway or LLMGateway.from_settings()
    graph = build_planner_graph(gw, retriever)
    final: PlannerState = await graph.ainvoke({"request": request, "warnings": []})
    return final["itinerary"]
