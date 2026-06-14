"""Assemble the planner graph: geocode -> gather -> compose -> critic -> (revise?).

S7 turns the linear slice into a multi-agent supervisor flow: the city worker
(geocode->gather->compose) drafts an itinerary, the critic validates it, and a
CAPPED corrective loop re-composes with the critic's feedback. The multi-city
fan-out coordinator + cross-city partial results arrive in S8. Gateway and the
optional retriever are closed over their nodes (never in serializable state).
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from tp_core.llm import LLMGateway

from tp_agents.checkpoint import make_checkpointer
from tp_agents.critic import critic_node
from tp_agents.nodes import PoiRetriever, compose_node, gather_node, geocode_node
from tp_agents.schemas import Itinerary, PlanRequest
from tp_agents.state import PlannerState

_MAX_COMPOSE_ATTEMPTS = 2  # 1 corrective re-compose (the containment cap, Decision 3)


def _should_revise(state: PlannerState) -> str:
    verdict = state.get("critic_verdict")
    attempts = state.get("compose_attempts", 1)
    max_attempts = state.get("max_compose_attempts", _MAX_COMPOSE_ATTEMPTS)
    if verdict is not None and verdict.has_issues and attempts < max_attempts:
        return "revise"
    return "end"


def build_planner_graph(
    gateway: LLMGateway, retriever: PoiRetriever | None = None, *, checkpointer: Any = None
) -> Any:
    """Compile the planner graph with gateway (+ optional retriever) bound to its nodes.

    A LangGraph ``checkpointer`` (S9b) persists in-run state so a crashed run resumes
    from the last completed node instead of redoing (and re-paying for) it.
    """
    builder = StateGraph(PlannerState)
    builder.add_node("geocode", geocode_node)

    async def gather(state: PlannerState) -> dict[str, Any]:
        return await gather_node(state, retriever=retriever)

    async def compose(state: PlannerState) -> dict[str, Any]:
        return await compose_node(state, gateway)

    async def critic(state: PlannerState) -> dict[str, Any]:
        return await critic_node(state, gateway)

    builder.add_node("gather", gather)
    builder.add_node("compose", compose)
    builder.add_node("critic", critic)
    builder.add_edge(START, "geocode")
    builder.add_edge("geocode", "gather")
    builder.add_edge("gather", "compose")
    builder.add_edge("compose", "critic")
    builder.add_conditional_edges("critic", _should_revise, {"revise": "compose", "end": END})
    return builder.compile(checkpointer=checkpointer)


async def run_graph(
    graph: Any, checkpointer: Any, thread_id: str | None, initial: PlannerState
) -> Any:
    """Invoke the graph, resuming from a saved checkpoint when one exists for this thread."""
    if checkpointer is None:
        return await graph.ainvoke(initial)
    config = {"configurable": {"thread_id": thread_id}}
    existing = await checkpointer.aget(config)  # resume (None input) iff a checkpoint exists
    return await graph.ainvoke(None if existing else initial, config=config)


async def plan(
    request: PlanRequest,
    *,
    gateway: LLMGateway | None = None,
    retriever: PoiRetriever | None = None,
    run_id: str | None = None,
) -> Itinerary:
    """Run the planner for one request and return the (critic-checked) itinerary.

    When ``run_id`` is set the run is checkpointed under that thread id, so a worker
    crash mid-run resumes from the last completed node on redelivery (S9b).
    """
    gw = gateway or LLMGateway.from_settings()
    initial: PlannerState = {
        "request": request,
        "warnings": [],
        "max_compose_attempts": _MAX_COMPOSE_ATTEMPTS,
    }
    async with make_checkpointer(run_id) as checkpointer:
        graph = build_planner_graph(gw, retriever, checkpointer=checkpointer)
        final: PlannerState = await run_graph(graph, checkpointer, run_id, initial)
    return final["itinerary"]
