"""Worker task runner: one loop per process, clean escapes, never run a finished run twice."""

from __future__ import annotations

import asyncio

import pytest
from tp_core.runs import RunRecord
from tp_worker import tasks


def test_every_task_shares_one_process_loop() -> None:
    """Tasks used to asyncio.run() - a new loop per run, destroyed after it. Process-wide
    clients then had their closes scheduled on dead loops ("Event loop is closed")."""
    seen: list[asyncio.AbstractEventLoop] = []

    async def probe() -> None:
        seen.append(asyncio.get_running_loop())

    tasks._run(probe())
    tasks._run(probe())
    assert seen[0] is seen[1] is tasks._loop()
    assert not seen[0].is_closed()


def test_an_escape_cancels_the_rest_of_the_task() -> None:
    """A Celery soft time limit raises from a signal handler - often while the loop is
    idle in select(), outside the task. The task must not survive into the next run."""
    cancelled: list[bool] = []

    async def long_run() -> None:
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    def escape() -> None:
        raise SystemExit  # a BaseException escapes run_until_complete, like the signal does

    tasks._loop().call_later(0.05, escape)
    with pytest.raises(SystemExit):
        tasks._run(long_run())
    assert cancelled == [True]
    tasks._run(asyncio.sleep(0))  # and the loop is still usable for the next task


def test_a_finished_run_is_never_executed_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """A redelivery after a lost ack, or a dispatch that landed after the API gave up,
    must not overwrite a truthful status - or bill the LLM a second time."""
    record = RunRecord(id="r1", kind="plan", status="failed",
                       request={"city": "Kyoto", "interests": ["temples"]})
    started: list[str] = []

    async def fake_get_run(run_id: str, **kwargs: object) -> RunRecord:
        return record

    async def fake_mark_running(run_id: str) -> None:
        started.append(run_id)

    monkeypatch.setattr(tasks, "get_run", fake_get_run)
    monkeypatch.setattr(tasks, "mark_running", fake_mark_running)
    tasks._run(tasks._run_plan("r1"))
    tasks._run(tasks._run_trip("r1"))
    assert started == []


# --- transient infrastructure errors are retried, not recorded as failures ----------------

class _Retry(Exception):
    pass


def _task(retries: int, calls: list[int]) -> object:
    from types import SimpleNamespace

    def retry(*, exc: BaseException, countdown: int) -> _Retry:
        calls.append(countdown)
        return _Retry()

    return SimpleNamespace(request=SimpleNamespace(retries=retries), retry=retry)


def test_a_dns_blip_is_retried_with_backoff() -> None:
    """A task that could not reach Postgres used to die and strand its run at `queued`."""
    calls: list[int] = []
    seen: list[bool] = []

    async def runner(run_id: str, *, final_attempt: bool) -> None:
        seen.append(final_attempt)
        raise OSError(-3, "Temporary failure in name resolution")

    with pytest.raises(_Retry):
        tasks._execute(_task(0, calls), runner, "r1")
    assert calls == [5] and seen == [False]


def test_the_last_attempt_lets_the_error_through() -> None:
    calls: list[int] = []
    seen: list[bool] = []

    async def runner(run_id: str, *, final_attempt: bool) -> None:
        seen.append(final_attempt)
        raise OSError("still down")

    with pytest.raises(OSError, match="still down"):
        tasks._execute(_task(tasks._MAX_INFRA_RETRIES, calls), runner, "r1")
    assert calls == [] and seen == [True]


def test_a_model_failure_is_never_retried() -> None:
    """'All venues exhausted' is a real answer - the failover drill expects it to FAIL."""
    from tp_core.exceptions import ProviderError

    calls: list[int] = []

    async def runner(run_id: str, *, final_attempt: bool) -> None:
        raise ProviderError("All providers exhausted for tier 'mid'.")

    with pytest.raises(ProviderError):
        tasks._execute(_task(0, calls), runner, "r1")
    assert calls == []


def test_a_retried_run_is_not_marked_failed_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """Marking it failed would make the retry skip it as terminal (_already_finished)."""
    record = RunRecord(id="r2", kind="plan", status="queued",
                       request={"city": "Kyoto", "interests": ["temples"]})
    failed: list[str] = []

    async def fake_get_run(run_id: str, **kwargs: object) -> RunRecord:
        return record

    async def noop(*args: object, **kwargs: object) -> None:
        return None

    async def boom(*args: object, **kwargs: object) -> None:
        raise OSError("Temporary failure in name resolution")

    async def fake_mark_failed(run_id: str, error: str, **kwargs: object) -> None:
        failed.append(error)

    monkeypatch.setattr(tasks, "get_run", fake_get_run)
    monkeypatch.setattr(tasks, "mark_running", noop)
    monkeypatch.setattr(tasks, "plan", boom)
    monkeypatch.setattr(tasks, "mark_failed", fake_mark_failed)
    with pytest.raises(OSError):
        tasks._run(tasks._run_plan("r2", final_attempt=False))
    assert failed == []  # left open for the retry
    with pytest.raises(OSError):
        tasks._run(tasks._run_plan("r2", final_attempt=True))
    assert len(failed) == 1  # the last attempt records the truth


# --- a run's cost is everything it SPENT (2026-10-01) ---------------------------------------

def _queued(run_id: str, kind: str = "plan") -> RunRecord:
    request: dict[str, object] = (
        {"city": "Kyoto", "interests": ["temples"]}
        if kind == "plan"
        else {"cities": ["Kyoto", "Osaka"], "interests": ["temples"], "days": 2}
    )
    return RunRecord(id=run_id, kind=kind, status="queued", request=request)


def _offline_runner(monkeypatch: pytest.MonkeyPatch, run_id: str, kind: str = "plan") -> None:
    """Fake the run's store; keep record_spend REAL so its per-run tally is under test."""
    from tp_core import control

    async def fake_get_run(rid: str, **kwargs: object) -> RunRecord:
        return _queued(rid, kind)

    async def noop(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(control, "_redis_allowed", lambda: False)  # tally only, no network
    monkeypatch.setattr(tasks, "get_run", fake_get_run)
    monkeypatch.setattr(tasks, "mark_running", noop)


@pytest.mark.parametrize("kind", ["plan", "trip"])
def test_a_failed_run_keeps_what_it_spent(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    """A failed run was always saved at $0, even after it had paid for a model call."""
    from tp_core.control import record_spend

    saved: list[float] = []
    observed: list[tuple[str, float]] = []

    async def pays_then_fails(*args: object, **kwargs: object) -> None:
        await record_spend(0.0025)  # a paid compose call...
        raise RuntimeError("...then every venue for the critic was down")

    async def fake_mark_failed(run_id: str, error: str, *, cost_usd: float = 0.0) -> None:
        saved.append(cost_usd)

    _offline_runner(monkeypatch, "r3", kind)
    monkeypatch.setattr(tasks, "plan" if kind == "plan" else "plan_trip", pays_then_fails)
    monkeypatch.setattr(tasks, "mark_failed", fake_mark_failed)
    monkeypatch.setattr(
        tasks, "record_run", lambda status, _d, cost: observed.append((status, cost))
    )
    runner = tasks._run_plan if kind == "plan" else tasks._run_trip
    with pytest.raises(RuntimeError):
        tasks._run(runner("r3"))
    assert saved == [0.0025]
    assert observed == [("failed", 0.0025)]


@pytest.mark.parametrize(
    ("graph_cost", "spends", "expected"),
    [
        (0.0, [0.000004, 0.0], 0.000004),  # local LLM is free, the query embedding is not
        (0.003, [0.003, 0.000004], 0.003004),  # paid compose + critic, plus the embedding
        (0.002, [], 0.002),  # a call that slipped past the tally never SHRINKS the figure
    ],
)
def test_a_succeeded_run_is_saved_at_its_true_cost(
    monkeypatch: pytest.MonkeyPatch, graph_cost: float, spends: list[float], expected: float
) -> None:
    """The graph's figure is compose + critic; the run also paid for what it never saw."""
    from tp_agents.schemas import Itinerary
    from tp_core.control import record_spend

    saved: list[tuple[float, float]] = []

    async def plans(*args: object, **kwargs: object) -> Itinerary:
        for usd in spends:
            await record_spend(usd)
        return Itinerary(city="Kyoto", summary_markdown="x", cost_usd=graph_cost)

    async def fake_mark_succeeded(
        run_id: str, result: Itinerary, *, cost_usd: float, warnings: list[str]
    ) -> None:
        saved.append((cost_usd, result.cost_usd))  # the column AND the stored result agree

    _offline_runner(monkeypatch, "r4")
    monkeypatch.setattr(tasks, "plan", plans)
    monkeypatch.setattr(tasks, "mark_succeeded", fake_mark_succeeded)
    tasks._run(tasks._run_plan("r4"))
    assert saved == [(expected, expected)]
