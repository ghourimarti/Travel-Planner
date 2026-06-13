"""Assemble the single-agent planner graph: geocode -> gather -> compose.

Deliberately linear for S4 (the walking skeleton). Conditional routing, a critic,
and per-city fan-out arrive in S7/S8. The gateway is closed over the compose node
so it never lives in (serializable) graph state.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from tp_core.llm import LLMGateway

from tp_agents.nodes import compose_node, gather_node, geocode_node
from tp_agents.schemas import Itinerary, PlanRequest
from tp_agents.state import PlannerState


def build_planner_graph(gateway: LLMGateway) -> Any:
    """Compile the planner graph with ``gateway`` bound to the compose node."""
    builder = StateGraph(PlannerState)
    builder.add_node("geocode", geocode_node)
    builder.add_node("gather", gather_node)

    async def compose(state: PlannerState) -> dict[str, Any]:
        return await compose_node(state, gateway)

    builder.add_node("compose", compose)
    builder.add_edge(START, "geocode")
    builder.add_edge("geocode", "gather")
    builder.add_edge("gather", "compose")
    builder.add_edge("compose", END)
    return builder.compile()


async def plan(request: PlanRequest, *, gateway: LLMGateway | None = None) -> Itinerary:
    """Run the planner for one request and return the grounded itinerary.

    ``gateway`` is injectable for tests; in production it's built lazily from
    settings (so importing this module never requires an API key).
    """
    gw = gateway or LLMGateway.from_settings()
    graph = build_planner_graph(gw)
    final: PlannerState = await graph.ainvoke({"request": request, "warnings": []})
    return final["itinerary"]
