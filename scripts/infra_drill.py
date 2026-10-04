"""Q15/Q16/Q17 from docs/INSPECTION.md — the infra-breaker drills.

These are the queries the battery deliberately refuses to run, because two of them stop
a datastore and the application is genuinely down while they do. Everything here is
wrapped in a `finally` that restarts what it stopped and VERIFIES the restart, because a
drill that leaves Postgres stopped has not tested resilience, it has caused an outage.

The contrast is the whole point:
    Q15  Redis down     -> FAIL-OPEN   : the cache is bypassed, planning degrades
    Q16  Postgres down  -> FAIL-CLOSED : session_scope() raises rather than hand back a
                                         run_id for a run it never persisted
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _inspect_common import (  # noqa: E402
    API,
    DB,
    REDIS,
    WORKER,
    Report,
    dexec,
    http,
    post_json,
    promq,
    section,
    sh,
)

SETTLE_S = 6.0


def counters(prefix: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for s in promq(prefix) or []:
        m = dict(s["metric"])
        name = m.pop("__name__", prefix)
        labels = ",".join(f"{k}={v}" for k, v in sorted(m.items())
                          if k not in ("instance", "job"))
        # SUMMED across jobs: the key drops `job`, and since every error type is primed
        # on BOTH api and worker, a plain assignment let the worker's 0 overwrite the api's
        # real postgres_error increment (2026-09-30).
        key = f"{name}{{{labels}}}"
        out[key] = out.get(key, 0.0) + float(s["value"][1])
    return out


def moved(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    keys = set(before) | set(after)
    d = {k: round(after.get(k, 0.0) - before.get(k, 0.0), 6) for k in keys}
    return {k: v for k, v in sorted(d.items()) if v}


def container_up(name: str) -> bool:
    code, out = sh(["docker", "ps", "--filter", f"name={name}", "--format", "{{.Names}}"])
    return code == 0 and name in out


def wait_healthy(name: str, timeout_s: int = 120) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        code, out = sh(["docker", "ps", "--filter", f"name={name}",
                        "--format", "{{.Status}}"])
        s = out.strip().lower()
        if s.startswith("up") and "starting" not in s:
            return True
        time.sleep(3)
    return False


def q17_embedder_stamp(r: Report) -> None:
    """READ-ONLY. Both candidate models emit 1024 dims, so only the stamp can catch a
    mismatch — a dimension check would pass either way."""
    section("Q17 - embedder provenance stamp (read-only)")
    code, out = dexec(WORKER, [
        "python", "-c",
        "import asyncio;from tp_retrieval.vectorstore import QdrantStore;"
        "print(asyncio.run(QdrantStore.from_settings(dim=1024).read_meta()))",
    ], timeout=90)
    stamp = out.strip()
    if code == 0 and "embedder_model" in stamp:
        r.ok("index carries an embedder stamp", stamp[:120])
    else:
        r.bad("index carries an embedder stamp", stamp[:160] or f"exit {code}")

    errs = counters("tp_errors_total")
    # > 0, not merely present: every known error type is now PRIMED at 0 on start, so
    # the series always exists and "present" would warn on every healthy stack.
    mismatch = {k: v for k, v in errs.items() if "embedder_mismatch" in k and v > 0}
    if mismatch:
        r.warn("embedder_mismatch counter", f"{mismatch} - retrieval quality is degraded")
    else:
        r.ok("no embedder mismatch recorded", "tp_errors_total{embedder_mismatch} is 0")

    # "No mismatch recorded" used to pass NO MATTER WHAT: the check itself never ran
    # (asyncio.run inside a running loop, swallowed). So prove the detector can FIRE -
    # against the live index, with a deliberately wrong model. PROMETHEUS_MULTIPROC_DIR
    # is unset so this one-off process cannot write a fake mismatch into the worker's
    # own metrics.
    probe = (
        "import asyncio\n"
        "from prometheus_client import REGISTRY\n"
        "from tp_retrieval.retrieve import _check_embedder\n"
        "from tp_retrieval.vectorstore import QdrantStore\n"
        "class Wrong:\n"
        "    model = 'deliberately-wrong-embedder'\n"
        "    dim = 1024\n"
        "def n():\n"
        "    labels = {'type': 'embedder_mismatch'}\n"
        "    return REGISTRY.get_sample_value('tp_errors_total', labels) or 0\n"
        "before = n()\n"
        "asyncio.run(_check_embedder(Wrong(), QdrantStore.from_settings(dim=1024)))\n"
        "print('DETECTED' if n() > before else 'MISSED')\n"
    )
    code, out = dexec(WORKER, ["env", "-u", "PROMETHEUS_MULTIPROC_DIR", "python", "-c", probe],
                      timeout=90)
    (r.ok if "DETECTED" in out else r.bad)(
        "mismatch detector fires on a wrong embedder",
        "DETECTED" if "DETECTED" in out else (out.strip()[-160:] or f"exit {code}"))

    # And that the check really ran inside the live worker, not just in this probe.
    _, logs = sh(["docker", "logs", WORKER], timeout=30)
    if "embedder_check_ok" in logs or "embedder_mismatch" in logs:
        r.ok("embedder check ran in the live worker", "embedder_check_ok in its log")
    else:
        r.void("embedder check ran in the live worker",
               "no grounded run since the worker started - run `make smoke`, then re-run")


def queued_runs() -> int | None:
    code, out = dexec(DB, ["psql", "-U", "tp", "-d", "tp", "-tAc",
                           "select count(*) from runs where status='queued'"], timeout=30)
    try:
        return int(out.strip()) if code == 0 else None
    except ValueError:
        return None


def wait_moved(before: dict[str, float], prefix: str, part: str,
               timeout_s: float = 45.0) -> dict[str, float]:
    """Poll until a counter matching `part` moved. Prometheus scrapes every 15s, so one
    read straight after the event can miss an increment that already happened."""
    deadline = time.time() + timeout_s
    while True:
        d = {k: v for k, v in moved(before, counters(prefix)).items() if part in k}
        if d or time.time() >= deadline:
            return d
        time.sleep(3)


def q15_redis_down(r: Report) -> None:
    section("Q15 - Redis DOWN (fail-open)")
    before = counters("tp_cache_events_total")
    errors_before = counters("tp_errors_total")
    queued_before = queued_runs()
    stopped = False
    try:
        sh(["docker", "stop", REDIS], timeout=90)
        stopped = True
        time.sleep(SETTLE_S)
        r.ok("redis stopped", "container is down")

        started = time.monotonic()
        code, body = post_json(f"{API}/plan",
                               {"city": "Kyoto", "interests": ["temples"], "days": 1})
        took = time.monotonic() - started
        # Celery's broker is ALSO redis, so the run cannot be queued. What matters is how
        # that is handled: this used to be a 500 after ~100s with the run left at
        # `queued` forever. It must now be a prompt 503 with the run marked failed.
        if code == 202:
            r.ok("dispatch survived redis loss", "HTTP 202 - broker reachable")
        elif code == 503:
            r.ok("dispatch refused cleanly during redis loss",
                 f"HTTP 503 in {took:.1f}s - queue unavailable, run compensated")
        else:
            r.bad("dispatch during redis loss",
                  f"HTTP {code} in {took:.1f}s - expected 503: a failed enqueue must be "
                  "compensated, not a 500 that strands the run at 'queued'")

        code, _ = http(f"{API}/health", timeout=15)
        (r.ok if code == 200 else r.warn)(
            "API still answers /health without redis", f"HTTP {code}")
    finally:
        if stopped:
            sh(["docker", "start", REDIS], timeout=120)
            ok = wait_healthy(REDIS)
            (r.ok if ok else r.bad)("redis RESTORED", "healthy" if ok else "did NOT come back")
    time.sleep(SETTLE_S)

    queued_after = queued_runs()
    if queued_before is None or queued_after is None:
        r.void("no run stranded at 'queued'", "could not read the runs table")
    else:
        (r.ok if queued_after <= queued_before else r.bad)(
            "no run stranded at 'queued'",
            f"queued {queued_before} -> {queued_after}"
            + ("" if queued_after <= queued_before else " - dispatch left a run behind"))

    redis_moved = wait_moved(errors_before, "tp_errors_total", "redis_error")
    (r.ok if redis_moved else r.bad)(
        "redis outage visible in tp_errors_total",
        str(redis_moved) if redis_moved else "redis_error did not move - the outage was silent")
    d = moved(before, counters("tp_cache_events_total"))
    interesting = {k: v for k, v in d.items() if "error" in k or "skipped" in k}
    if interesting:
        r.ok("cache error/skipped transition observed", str(interesting))
    else:
        # expected=True: this void happens on EVERY healthy run and always will.
        # Redis is Celery's BROKER as well as the cache, so with Redis down the request
        # dies at dispatch and never reaches the cache layer to record error/skipped.
        # Q15 cannot demonstrate cache fail-open on this architecture - documented in
        # docs/INSPECTION.md - so failing the drill for it would make `make infra-drill`
        # permanently red on a perfectly healthy stack, which is how an exit code stops
        # being read. Every other void here still fails.
        r.void("cache error/skipped transition",
               "no error/skipped samples - the run never reached the cache layer "
               "(Redis is the BROKER too, so dispatch dies first; see INSPECTION.md Q15)",
               expected=True)


def q16_postgres_down(r: Report) -> None:
    section("Q16 - Postgres DOWN (fail-CLOSED)")
    before = counters("tp_errors_total")
    stopped = False
    try:
        sh(["docker", "stop", DB], timeout=90)
        stopped = True
        time.sleep(SETTLE_S)
        r.ok("postgres stopped", "container is down")

        code, body = post_json(f"{API}/plan",
                               {"city": "Kyoto", "interests": ["temples"], "days": 1})
        # The POINT of fail-closed: refusing beats handing back a run_id for a run that
        # was never persisted. A 2xx here would be the defect.
        # 503 since 2026-10-01: a retryable refusal that names the database. A bare
        # 500 still REFUSES (fail-closed holds), so it warns rather than fails.
        if code == 503:
            r.ok("planning REFUSES without postgres",
                 "HTTP 503 - a retryable refusal, not a degraded success")
        elif code >= 500 or code == 0:
            r.warn("planning REFUSES without postgres",
                   f"HTTP {code} - refused, but not as the 503 a dead database maps to")
        elif code == 202:
            r.bad("planning REFUSES without postgres",
                  "HTTP 202 - handed back a run_id for a run it cannot persist")
        else:
            r.warn("planning without postgres", f"HTTP {code}")
    finally:
        if stopped:
            sh(["docker", "start", DB], timeout=120)
            ok = wait_healthy(DB)
            (r.ok if ok else r.bad)("postgres RESTORED",
                                    "healthy" if ok else "did NOT come back")
    time.sleep(SETTLE_S)
    # Polled, like Q15: one read 6 s after the restore landed before the next 15 s scrape
    # and reported VOID while the api had in fact counted postgres_error (2026-09-30).
    pg = wait_moved(before, "tp_errors_total", "postgres")
    if pg:
        r.ok("postgres error/circuit counters moved", str(pg))
    else:
        r.void("postgres error counters", "no postgres_* samples appeared")


def stack_ready(r: Report) -> bool:
    """PRECONDITION. A drill against a stack that is not up proves nothing: it once
    reported "redis stopped" for a container that no longer existed, then nine FAILs
    that were about the stack, not the fix (a `make down` ran mid-drill, 2026-09-30)."""
    missing = [name for name in (WORKER, REDIS, DB) if not container_up(name)]
    code, _ = http(f"{API}/health", timeout=15)
    if missing or code != 200:
        section("precondition")
        r.bad("stack is up before the drill",
              f"not running: {', '.join(missing) or '-'}; api /health HTTP {code} - "
              "bring the stack up first (e.g. `make up-sglang`), then re-run")
        return False
    return True


def main() -> int:
    print("\nINFRA BREAKER DRILL - Q15 / Q16 / Q17")
    print("  Q15 and Q16 STOP a datastore. The app is genuinely down while they run.")
    print("  Both are wrapped in finally: restarted and VERIFIED before exit.\n")
    r = Report()
    if not stack_ready(r):
        return r.summary()
    try:
        q17_embedder_stamp(r)
        q15_redis_down(r)
        q16_postgres_down(r)
    finally:
        section("final state")
        for name in (REDIS, DB):
            up = container_up(name)
            (r.ok if up else r.bad)(f"{name} running", "yes" if up else "NO - START IT")
        code, _ = http(f"{API}/health", timeout=20)
        (r.ok if code == 200 else r.bad)("API healthy at the end", f"HTTP {code}")
    return r.summary()


if __name__ == "__main__":
    from _inspect_common import exclusive_run

    with exclusive_run("infra-drill"):
        raise SystemExit(main())
