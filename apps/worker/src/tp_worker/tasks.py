"""Celery tasks: run the planner graph off the request thread.

Each sync task drives the async LangGraph on ONE event loop per worker process (see
``_loop``). The request is loaded from Postgres by ``run_id`` — never passed through
Celery — so there's nothing to (de)serialize but a string. A failure is recorded on
the run AND re-raised so Celery (acks_late) also marks the task failed.
"""

from __future__ import annotations

import asyncio
import atexit
import time
from collections.abc import Coroutine
from contextlib import suppress
from functools import lru_cache
from typing import Any

from sqlalchemy.exc import InterfaceError, OperationalError
from tp_agents import PlanRequest, TripRequest, plan, plan_trip
from tp_agents.nodes import PoiRetriever
from tp_agents.schemas import Itinerary, TripItinerary
from tp_core.celery import celery_app
from tp_core.control import track_run_spend
from tp_core.events import run_publisher
from tp_core.logging import get_logger
from tp_core.metrics import record_run
from tp_core.runs import RunStatus, get_run, mark_failed, mark_running, mark_succeeded

_log = get_logger("tp_worker.tasks")
_TERMINAL = {RunStatus.succeeded.value, RunStatus.failed.value}

#: Infrastructure blips worth a RETRY: Postgres / Redis / DNS unreachable for a moment.
#: OSError covers socket.gaierror ("Temporary failure in name resolution") and refused
#: connections. A task used to die on the first one - and if it died before it could write
#: the run (Postgres being the thing that was unreachable), the run stayed `queued`
#: forever: 4 runs were stranded that way under load (2026-09-30). Model failures are NOT
#: here: ProviderError ("all venues exhausted") is a real answer and fails the run at once.
_TRANSIENT_INFRA: tuple[type[BaseException], ...] = (OSError, OperationalError, InterfaceError)
_INFRA_RETRY_COUNTDOWNS_S = (5, 15, 30)
_MAX_INFRA_RETRIES = len(_INFRA_RETRY_COUNTDOWNS_S)


@lru_cache(maxsize=1)
def _loop() -> asyncio.AbstractEventLoop:
    """ONE event loop per worker process, reused by every task.

    Tasks used to call ``asyncio.run()``: build a loop, run, DESTROY it - per task. But
    the retriever and its OpenAI embedding client are cached per PROCESS, and the OpenAI
    SDK closes an HTTP client by scheduling ``aclose()`` on the running loop when it is
    garbage-collected. With the loop torn down after every run those closes landed on a
    dying loop ("RuntimeError: Event loop is closed" in the worker log), and a
    process-wide client could be handed a connection whose loop no longer existed. A
    process-lifetime loop matches the process-lifetime objects.

    Lazy, so a prefork child builds its own after the fork instead of inheriting one.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    atexit.register(loop.close)
    return loop


def _run(coro: Coroutine[Any, Any, None]) -> None:
    """Drive one task on the process loop; on ANY escape, cancel what is left of it.

    ``asyncio.run()`` guaranteed that by cancelling leftover tasks on exit. A Celery soft
    time limit raises from a signal handler, possibly while the loop sits in select()
    rather than inside the task - so without this, a timed-out run would carry on
    executing in the background during the NEXT task.
    """
    loop = _loop()
    task = loop.create_task(coro)
    try:
        loop.run_until_complete(task)
    except BaseException:
        if not task.done():
            task.cancel()
            with suppress(BaseException):
                loop.run_until_complete(task)
        raise


def _already_finished(run_id: str, status: str) -> bool:
    """A terminal run is never executed again.

    Two ways a task can arrive for a run that is already over: a redelivery after its
    ack was lost (acks_late - see celery.py), or a dispatch that landed AFTER the API
    gave up waiting and marked the run failed (tp_api.main._dispatch). Running it would
    overwrite a truthful status and bill the LLM a second time.
    """
    if status in _TERMINAL:
        _log.warning("run_already_finished_skipped", run_id=run_id, status=status)
        return True
    return False


@lru_cache
def _retriever() -> PoiRetriever | None:
    """Build the corpus retriever once per worker process; ``None`` if unavailable."""
    try:
        from tp_retrieval import get_retriever

        return get_retriever()
    except Exception:  # no key / no Qdrant -> fall back to live tools
        return None


def _with_true_cost[C: (Itinerary, TripItinerary)](result: C, spent: list[float]) -> C:
    """Stamp the run's TRUE cost - everything it spent - on the result before saving.

    The graph's own figure is compose + critic; the run tally (track_run_spend) also
    has the query embedding and the reranker. max(), not the tally alone: the graph's
    figure can only be lower, and if a call ever slipped past the tally the graph's
    number still stands instead of shrinking.
    """
    total = round(max(result.cost_usd, spent[0]), 6)
    return result.model_copy(update={"cost_usd": total})


def _will_retry(exc: BaseException, final_attempt: bool) -> bool:
    """A transient infra error before the last attempt is RETRIED, not recorded as failed.

    Marking the run failed first would make the retry skip it as terminal
    (``_already_finished``), turning a two-second DNS blip into a failed plan.
    """
    return isinstance(exc, _TRANSIENT_INFRA) and not final_attempt


async def _run_plan(run_id: str, *, final_attempt: bool = True) -> None:
    record = await get_run(run_id)
    if record is None or _already_finished(run_id, record.status):
        return
    await mark_running(run_id)
    start = time.monotonic()
    spent = track_run_spend()
    async with run_publisher(run_id) as emit:

        async def on_event(node: str, delta: Any, *, city: str | None = None) -> None:
            await emit("node", node=node, city=city)

        try:
            itinerary = await plan(
                PlanRequest.model_validate(record.request),
                retriever=_retriever(),
                run_id=run_id,
                tenant_id=record.tenant_id,
                on_event=on_event,
            )
            itinerary = _with_true_cost(itinerary, spent)
            await mark_succeeded(
                run_id, itinerary, cost_usd=itinerary.cost_usd, warnings=itinerary.warnings
            )
            record_run("succeeded", time.monotonic() - start, itinerary.cost_usd)
            await emit("done")
        except Exception as exc:
            if _will_retry(exc, final_attempt):
                raise
            # A failed run is not a free one: keep what it spent before failing.
            cost = round(spent[0], 6)
            record_run("failed", time.monotonic() - start, cost)
            await mark_failed(run_id, f"{type(exc).__name__}: {exc}", cost_usd=cost)
            await emit("failed", detail=str(exc))
            raise


async def _run_trip(run_id: str, *, final_attempt: bool = True) -> None:
    record = await get_run(run_id)
    if record is None or _already_finished(run_id, record.status):
        return
    await mark_running(run_id)
    start = time.monotonic()
    spent = track_run_spend()
    async with run_publisher(run_id) as emit:

        async def on_event(node: str, delta: Any, *, city: str | None = None) -> None:
            await emit("node", node=node, city=city)

        try:
            trip = await plan_trip(
                TripRequest.model_validate(record.request),
                retriever=_retriever(),
                run_id=run_id,
                tenant_id=record.tenant_id,
                on_event=on_event,
            )
            trip = _with_true_cost(trip, spent)
            await mark_succeeded(run_id, trip, cost_usd=trip.cost_usd, warnings=trip.warnings)
            record_run("succeeded", time.monotonic() - start, trip.cost_usd)
            await emit("done")
        except Exception as exc:
            if _will_retry(exc, final_attempt):
                raise
            # A failed run is not a free one: keep what it spent before failing.
            cost = round(spent[0], 6)
            record_run("failed", time.monotonic() - start, cost)
            await mark_failed(run_id, f"{type(exc).__name__}: {exc}", cost_usd=cost)
            await emit("failed", detail=str(exc))
            raise


def _execute(task: Any, runner: Any, run_id: str) -> None:
    """Run one attempt; on a transient infra error, schedule a retry with backoff.

    The retry covers the failure that stranded runs: Postgres unreachable at the very
    start (``get_run`` / ``mark_running``), before the run could be written at all. If the
    LAST attempt still cannot reach Postgres, the run stays open for the reconciler
    (``tp_core.runs.reconcile_orphans``), which closes it once nothing is in flight.
    """
    attempt = int(task.request.retries or 0)
    final = attempt >= _MAX_INFRA_RETRIES
    try:
        _run(runner(run_id, final_attempt=final))
    except _TRANSIENT_INFRA as exc:
        if final:
            raise
        countdown = _INFRA_RETRY_COUNTDOWNS_S[attempt]
        _log.warning("run_retry_scheduled", run_id=run_id, attempt=attempt + 1,
                     countdown_s=countdown, error=repr(exc))
        raise task.retry(exc=exc, countdown=countdown) from exc


@celery_app.task(name="tp_worker.tasks.plan_task", bind=True, max_retries=_MAX_INFRA_RETRIES)
def plan_task(self: Any, run_id: str) -> None:
    _execute(self, _run_plan, run_id)


@celery_app.task(name="tp_worker.tasks.trip_task", bind=True, max_retries=_MAX_INFRA_RETRIES)
def trip_task(self: Any, run_id: str) -> None:
    _execute(self, _run_trip, run_id)
