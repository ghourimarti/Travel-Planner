"""Assemble the planner graph: geocode -> gather -> compose -> critic -> (revise?).

S7 turns the linear slice into a multi-agent supervisor flow: the city worker
(geocode->gather->compose) drafts an itinerary, the critic validates it, and a
CAPPED corrective loop re-composes with the critic's feedback. The multi-city
fan-out coordinator + cross-city partial results arrive in S8. Gateway and the
optional retriever are closed over their nodes (never in serializable state).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.graph import END, START, StateGraph
from tp_core.llm import LLMGateway
from tp_core.metrics import record_revision
from tp_core.settings import DEFAULT_MAX_COST_USD
from tp_core.tracing import get_tracer

from tp_agents.checkpoint import make_checkpointer
from tp_agents.critic import critic_node
from tp_agents.nodes import PoiRetriever, compose_node, gather_node, geocode_node
from tp_agents.schemas import Itinerary, PlanRequest
from tp_agents.state import PlannerState

_MAX_COMPOSE_ATTEMPTS = 2  # 1 corrective re-compose (the containment cap, Decision 3)


def _should_revise(state: PlannerState) -> str:
    itinerary = state.get("itinerary")
    cost = itinerary.cost_usd if itinerary is not None else 0.0
    if cost >= state.get("max_cost_usd", DEFAULT_MAX_COST_USD):  # cost cap (Decision 20)
        return "end"
    verdict = state.get("critic_verdict")
    attempts = state.get("compose_attempts", 1)
    max_attempts = state.get("max_compose_attempts", _MAX_COMPOSE_ATTEMPTS)
    if verdict is not None and verdict.has_issues and attempts < max_attempts:
        record_revision()
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

    async def geocode(state: PlannerState) -> dict[str, Any]:
        with get_tracer().start_as_current_span("agent.geocode"):
            return await geocode_node(state)

    async def gather(state: PlannerState) -> dict[str, Any]:
        with get_tracer().start_as_current_span("agent.gather"):
            return await gather_node(state, retriever=retriever)

    async def compose(state: PlannerState) -> dict[str, Any]:
        with get_tracer().start_as_current_span("agent.compose"):
            return await compose_node(state, gateway)

    async def critic(state: PlannerState) -> dict[str, Any]:
        with get_tracer().start_as_current_span("agent.critic") as span:
            result = await critic_node(state, gateway)
            verdict = result.get("critic_verdict")
            if verdict is not None:
                span.set_attribute("critic.ok", verdict.ok)
                span.set_attribute("critic.has_issues", verdict.has_issues)
                span.set_attribute("critic.issue_count", len(verdict.issues))
                span.set_attribute("critic.invented_count", len(verdict.invented_places))
            return result

    builder.add_node("geocode", geocode)
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


async def stream_graph(
    graph: Any,
    checkpointer: Any,
    thread_id: str | None,
    initial: PlannerState,
    on_event: Callable[..., Awaitable[None]],
) -> Any:
    """Stream the graph, emit one event per completed node, and return the final state."""
    config = {"configurable": {"thread_id": thread_id}}
    input_ = None if await checkpointer.aget(config) else initial
    async for chunk in graph.astream(input_, config=config, stream_mode="updates"):
        for node in chunk:
            await on_event(node, chunk[node])
    snapshot = await graph.aget_state(config)
    return snapshot.values


async def plan(
    request: PlanRequest,
    *,
    gateway: LLMGateway | None = None,
    retriever: PoiRetriever | None = None,
    run_id: str | None = None,
    tenant_id: str | None = None,
    on_event: Callable[..., Awaitable[None]] | None = None,
) -> Itinerary:
    """Run the planner for one request and return the (critic-checked) itinerary.

    ``run_id`` checkpoints the run for resume (S9b). ``tenant_id`` scopes corpus retrieval
    to the caller's ACL (S12c). ``on_event`` (worker-only) streams a progress event per
    completed node (S9c); without it the graph is invoked directly.
    """
    gw = gateway or LLMGateway.from_settings()
    initial: PlannerState = {
        "request": request,
        "warnings": [],
        "max_compose_attempts": _MAX_COMPOSE_ATTEMPTS,
        "max_cost_usd": DEFAULT_MAX_COST_USD,
        "tenant_id": tenant_id,
    }
    with get_tracer().start_as_current_span("agent.plan") as span:
        span.set_attribute("run.id", run_id or "sync")
        span.set_attribute("plan.city", request.city)
        async with make_checkpointer(run_id) as checkpointer:
            graph = build_planner_graph(gw, retriever, checkpointer=checkpointer)
            if on_event is not None and checkpointer is not None:
                final: PlannerState = await stream_graph(
                    graph, checkpointer, run_id, initial, on_event
                )
            else:
                final = await run_graph(graph, checkpointer, run_id, initial)
        itinerary = final["itinerary"]
        span.set_attribute("run.cost_usd", round(itinerary.cost_usd, 6))
        return itinerary
