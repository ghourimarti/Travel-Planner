"""Cost controls: a static floor, a runtime kill switch, and a daily spend breaker.

THREE CONTROLS, DELIBERATELY LAYERED
------------------------------------
    LLM_ENABLED            a STATIC floor an operator sets in config
    planning:enabled       a RUNTIME switch ops flip live with redis-cli
    DAILY_SPEND_LIMIT_USD  an AUTOMATIC breaker that trips on accumulated spend

They are not three names for the same thing. The floor can only ever DISABLE: if
``LLM_ENABLED`` is false, no Redis value re-enables generation. That ordering is the
point — an operator's deliberate decision has to outrank a flag someone set at 3am
and forgot, otherwise "we turned it off" is not a statement you can rely on.

The runtime switch is the reverse trade: it exists to be flipped *now*, without a
redeploy, when spend or an incident demands it.

FAIL-OPEN, EXCEPT WHERE IT MUST NOT BE
--------------------------------------
A missing key or a Redis blip leaves planning ENABLED, so an infra hiccup cannot take
the product down. The floor is the exception: it is read from config, not Redis, so
it cannot fail open — there is nothing to fail.

WHY DAILY SPEND IS SEPARATE FROM ``max_cost_usd``
-------------------------------------------------
``max_cost_usd`` caps ONE itinerary. It cannot answer "how much of this month went to
the paid leg because the GPU was down", which is exactly the question a serving chain
exists to make answerable. A per-request cap and a rolling budget catch different
failures: one runaway request, versus a thousand ordinary ones on an expensive venue.
"""

from __future__ import annotations

import os
from contextlib import suppress
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, Literal

import redis.asyncio as aioredis

from tp_core.llm.circuit import infra_breaker
from tp_core.logging import get_logger
from tp_core.metrics import record_error
from tp_core.settings import DEFAULT_REDIS_URL

_log = get_logger("tp_core.control")

# READ FROM THE ENVIRONMENT, NOT FROM Settings, and deliberately so.
#
# `get_settings()` validates the ENTIRE config, so calling it here would make a
# missing OPENAI_API_KEY break the KILL SWITCH — a cost control that stops working
# when the config is incomplete is worse than none, because it fails in exactly the
# situation you reached for it. settings.py already reserves this pattern for the
# dispatch path (see DEFAULT_DATABASE_URL / DEFAULT_REDIS_URL): persistence and
# dispatch must stand up without a provider key, and this module is on that path.
#
# Found by the existing tests, which failed the moment this module started importing
# get_settings(). Fixing the code rather than the tests: the tests were right.
_TRUE = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    return default if raw is None or raw == "" else raw.strip().lower() in _TRUE


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        _log.warning("control_env_not_a_number", var=name, value=raw)
        return default

_KEY = "planning:enabled"
_DISABLED = {b"0", b"false", "0", "false"}

#: Spend accumulates under a DAY-KEYED name with a TTL, so the key expires on its own.
#: A cleanup job that must run for a cost control to keep working is a cost control
#: with a second thing that can be broken.
_SPEND_KEY = "spend:usd:{day}"
_SPEND_TTL = 48 * 3600  # comfortably longer than the window it covers

SpendState = Literal["ok", "soft_alert", "breached"]

#: Per-RUN spend tally (see track_run_spend). None outside a worker run, so the API, the
#: eval CLI and every test record exactly as before.
_RUN_SPEND: ContextVar[list[float] | None] = ContextVar("tp_run_spend", default=None)


def track_run_spend() -> list[float]:
    """Start a per-run spend tally; ``record_spend`` adds every paid call to it.

    A run's own cost used to be compose + critic only, as the graph adds them up. It
    never saw the query embedding (real money even when the LLM is local), the
    reranker, or anything spent before the run FAILED - a failed run always read $0.
    record_spend() is the one place every paid call already reports to (the LLM
    gateway and the embedder), so tallying here gives the run's true cost.

    A one-element list rather than a float: tasks created inside the run (LangGraph
    branches, asyncio.gather) run in a COPY of the context that holds the same list
    object - so their spend lands in this total instead of in a discarded copy.
    """
    tally = [0.0]
    _RUN_SPEND.set(tally)
    return tally


def _redis_url() -> str:
    return os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _client() -> Any:
    return aioredis.from_url(  # type: ignore[no-untyped-call]  # redis async API
        _redis_url(), socket_connect_timeout=0.25
    )


def _redis_allowed() -> bool:
    """Whether to attempt Redis at all.

    record_spend() now runs on EVERY LLM call. Unguarded, a dead Redis would add its
    0.25s connect timeout to every one of them — turning a broken cost recorder into
    latency on 100% of traffic. Same trap the cache breaker exists to prevent, so it
    reuses the same breaker: one Redis, one piece of state about whether it is up.
    """
    return infra_breaker("redis").allows("redis")


async def record_spend(usd: float) -> None:
    """Add ``usd`` to today's running total. Best-effort: never fails a request.

    Recorded even when 0.0, so a self-hosted day is visibly zero rather than absent —
    "no data" and "no spend" must not look the same on a cost dashboard.
    """
    if usd < 0:
        return
    tally = _RUN_SPEND.get()
    if tally is not None:  # before any Redis check: a run's cost must not need Redis
        tally[0] += usd
    if not _redis_allowed():
        return
    client: Any = None
    try:
        client = _client()
        key = _SPEND_KEY.format(day=_today())
        await client.incrbyfloat(key, usd)
        await client.expire(key, _SPEND_TTL)
    except Exception:  # best-effort, but COUNTED: a spend ledger that silently stops
        record_error("redis_error")  # recording is a breaker that can never trip
    finally:
        if client is not None:
            with suppress(Exception):
                await client.aclose()


async def spend_today() -> float:
    """Today's accumulated spend in USD, or 0.0 if it cannot be read."""
    client: Any = None
    raw: Any = None
    try:
        client = _client()
        raw = await client.get(_SPEND_KEY.format(day=_today()))
    except Exception:
        record_error("redis_error")
        return 0.0
    finally:
        if client is not None:
            with suppress(Exception):
                await client.aclose()
    if raw is None:
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


async def spend_state() -> SpendState:
    """Where today's spend sits against the daily limit.

    A limit of 0 disables the breaker entirely, which is the shipped default: adding
    this module must not start refusing traffic on somebody's existing deployment.
    """
    limit = _env_float("DAILY_SPEND_LIMIT_USD", 0.0)
    if limit <= 0:
        return "ok"
    spent = await spend_today()
    if spent >= limit:
        return "breached"
    if spent >= limit * _env_float("SPEND_SOFT_ALERT_RATIO", 0.8):
        return "soft_alert"
    return "ok"


async def planning_enabled() -> bool:
    """True unless a floor, a switch, or the spend breaker says otherwise.

    Checked in that order, cheapest and most authoritative first: the config floor
    needs no I/O and cannot be overridden, so consulting Redis before it would be
    both slower and wrong.
    """
    if not _env_bool("LLM_ENABLED", True):
        return False  # FLOOR: no runtime value can lift this

    client: Any = None
    value: Any = None
    try:
        client = _client()
        value = await client.get(_KEY)
    except Exception:  # fail-open (see module docstring) - but counted, never silent
        record_error("redis_error")
    finally:
        if client is not None:
            with suppress(Exception):
                await client.aclose()
    if value is not None and value in _DISABLED:
        return False

    if await spend_state() == "breached":
        _log.warning(
            "spend_breaker_open",
            limit_usd=_env_float("DAILY_SPEND_LIMIT_USD", 0.0),
            spent_usd=await spend_today(),
        )
        return False
    return True
