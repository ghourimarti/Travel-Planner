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
        out[f"{name}{{{labels}}}"] = float(s["value"][1])
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
    mismatch = {k: v for k, v in errs.items() if "embedder_mismatch" in k}
    if mismatch:
        r.warn("embedder_mismatch counter", f"{mismatch} - retrieval quality is degraded")
    else:
        r.ok("no embedder mismatch recorded", "tp_errors_total has no embedder_mismatch")


def q15_redis_down(r: Report) -> None:
    section("Q15 - Redis DOWN (fail-open)")
    before = counters("tp_cache_events_total")
    stopped = False
    try:
        sh(["docker", "stop", REDIS], timeout=90)
        stopped = True
        time.sleep(SETTLE_S)
        r.ok("redis stopped", "container is down")

        code, body = post_json(f"{API}/plan",
                               {"city": "Kyoto", "interests": ["temples"], "days": 1})
        # The doc warns that Celery's broker is ALSO redis, so dispatch itself may fail.
        # Report what actually happened rather than what would be tidy.
        if code == 202:
            r.ok("dispatch survived redis loss", "HTTP 202 - broker reachable")
        else:
            r.warn("dispatch during redis loss",
                   f"HTTP {code} - Celery's broker IS redis, so dispatch cannot queue. "
                   "Fail-open applies to the CACHE, not to the queue.")

        code, _ = http(f"{API}/health", timeout=15)
        (r.ok if code == 200 else r.warn)(
            "API still answers /health without redis", f"HTTP {code}")
    finally:
        if stopped:
            sh(["docker", "start", REDIS], timeout=120)
            ok = wait_healthy(REDIS)
            (r.ok if ok else r.bad)("redis RESTORED", "healthy" if ok else "did NOT come back")
    time.sleep(SETTLE_S)
    d = moved(before, counters("tp_cache_events_total"))
    interesting = {k: v for k, v in d.items() if "error" in k or "skipped" in k}
    if interesting:
        r.ok("cache error/skipped transition observed", str(interesting))
    else:
        r.void("cache error/skipped transition",
               "no error/skipped samples - the run never reached the cache layer")


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
        if code >= 500 or code == 0:
            r.ok("planning REFUSES without postgres",
                 f"HTTP {code} - clean error, not a degraded success")
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
    d = moved(before, counters("tp_errors_total"))
    pg = {k: v for k, v in d.items() if "postgres" in k}
    if pg:
        r.ok("postgres error/circuit counters moved", str(pg))
    else:
        r.void("postgres error counters", "no postgres_* samples appeared")


def main() -> int:
    print("\nINFRA BREAKER DRILL - Q15 / Q16 / Q17")
    print("  Q15 and Q16 STOP a datastore. The app is genuinely down while they run.")
    print("  Both are wrapped in finally: restarted and VERIFIED before exit.\n")
    r = Report()
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
    raise SystemExit(main())
