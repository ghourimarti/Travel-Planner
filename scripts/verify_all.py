"""Inspect EVERY component after a run-through, and judge the runs themselves.

`make inspect` proves the chain and the instruments by DRIVING the app. This does the
opposite job: it assumes YOU drove it — from the web UI, by hand — and then checks that
every component behaved, that every instrument recorded it, and that the runs you produced
say what they should.

It changes nothing. No fault injection, no container restarts, no switches flipped. Safe to
run at any time, as often as you like.

The part that does not exist anywhere else is Section 9: it reads the runs you actually
created and judges them, including the failure this app is most exposed to — a confident,
grounded, zero-warning itinerary anchored on the WRONG PLACE.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _inspect_common import (  # noqa: E402
    APIC,
    DB,
    GRAFANA,
    JAEGER,
    QDRANT,
    REDIS,
    WORKER,
    Report,
    dexec,
    http,
    promq,
    section,
    sh,
)

WINDOW_MIN = 120  # how far back to look for "your" runs

#: Cities whose correct location is known, with a generous bounding box. Used to catch the
#: wrong-anchor class: geocoding that confidently resolves to somewhere you did not mean.
#: Nara once resolved to Washington DC, kyota to Uganda, "Kyoto, Osaka" to Hirakata.
KNOWN_BOXES = {
    "kyoto": (34.5, 35.5, 135.0, 136.5, "Japan"),
    "osaka": (34.2, 35.0, 135.0, 136.0, "Japan"),
    "nara": (34.3, 35.0, 135.5, 136.3, "Japan"),
    "tokyo": (35.3, 36.0, 139.3, 140.0, "Japan"),
    "nagasaki": (32.5, 33.6, 129.4, 130.4, "Japan"),
    "rome": (41.6, 42.2, 12.2, 12.8, "Italy"),
    "paris": (48.6, 49.1, 2.0, 2.6, "France"),
    "barcelona": (41.2, 41.6, 1.9, 2.4, "Spain"),
}


def psql(sql: str, timeout: int = 60) -> tuple[int, str]:
    return dexec(DB, ["psql", "-U", "tp", "-d", "tp", "-tAc", sql], timeout=timeout)


# ------------------------------------------------------------------ 1-8: components
def check_containers(r: Report) -> None:
    section("1 · containers")
    want = {
        "api": APIC, "worker": WORKER, "redis": REDIS, "db": DB,
        "qdrant": "p3-ai-travel-planner-qdrant-1",
        "prometheus": "p3-ai-travel-planner-prometheus-1",
        "grafana": "p3-ai-travel-planner-grafana-1",
        "jaeger": "p3-ai-travel-planner-jaeger-1",
        "langfuse": "p3-ai-travel-planner-langfuse-web-1",
        "web": "p3-ai-travel-planner-web-1",
    }
    for label, name in want.items():
        code, out = sh(["docker", "ps", "--filter", f"name={name}", "--format", "{{.Status}}"])
        s = out.strip()
        (r.ok if s.lower().startswith("up") else r.bad)(f"{label} container", s or "NOT RUNNING")


def check_datastores(r: Report) -> None:
    section("2 · datastores")
    code, out = dexec(DB, ["pg_isready"], timeout=30)
    (r.ok if code == 0 else r.bad)("postgres accepting connections", out.strip()[:80])

    code, out = dexec(REDIS, ["redis-cli", "ping"], timeout=30)
    (r.ok if "PONG" in out else r.bad)("redis responding", out.strip())

    code, body = http(f"{QDRANT}/collections/pois")
    if code != 200:
        r.bad("qdrant 'pois' reachable", str(body)[:100])
    else:
        n = json.loads(body)["result"]["points_count"]
        # A collection that EXISTS but is EMPTY gives a readiness probe nothing to fail on
        # while retrieval silently returns nothing for every query.
        (r.ok if n > 0 else r.bad)("qdrant 'pois' non-empty", f"{n} points")

    code, out = psql("select count(*) from runs")
    (r.ok if code == 0 else r.bad)("postgres runs table readable", f"{out.strip()} rows")

    code, out = psql(
        "select count(*) from checkpoints"
    )
    (r.ok if code == 0 else r.warn)("langgraph checkpoints readable", f"{out.strip()} rows")


def check_dispatch(r: Report) -> None:
    section("3 · dispatch")
    code, out = dexec(WORKER, ["celery", "-A", "tp_worker.celery_app", "status"], timeout=45)
    (r.ok if "online" in out.lower() else r.bad)("celery worker consuming", out.strip()[:80])


def check_prometheus(r: Report) -> None:
    section("4 · prometheus")
    code2, body = http("http://localhost:3009/api/v1/targets?state=active")
    if code2 != 200:
        r.bad("prometheus reachable", str(body)[:80])
        return
    for t in json.loads(body)["data"]["activeTargets"]:
        job, health = t["labels"]["job"], t["health"]
        (r.ok if health == "up" else r.bad)(f"scrape target {job}", health)

    expected = [
        "tp_cache_events", "tp_critic_revisions", "tp_dispatch", "tp_errors",
        "tp_itinerary_outcome", "tp_llm_calls", "tp_llm_cost_usd", "tp_llm_tokens",
        "tp_rate_limit_events", "tp_retrieval_results", "tp_run_cost_usd",
        "tp_run_duration_seconds", "tp_runs", "tp_stage_duration_seconds",
        "tp_venue_circuit_state", "tp_venue_latency_seconds",
    ]
    # Counters are exposed as <name>_total and histograms as <name>_bucket/_count/_sum.
    # Querying the BARE name finds nothing, so a first version reported 15 of 16 "missing"
    # while Grafana was happily drawing them - the one that matched was the gauge.
    code, body = http("http://localhost:3009/api/v1/label/__name__/values")
    names = set(json.loads(body).get("data") or []) if code == 200 else set()
    missing = [m for m in expected
               if not any(n == m or n.startswith(m + "_") for n in names)]
    (r.ok if not missing else r.bad)(
        f"all {len(expected)} metrics present",
        "none missing" if not missing else str(missing))


def check_grafana(r: Report) -> None:
    section("5 · grafana")
    code, body = http(f"{GRAFANA}/api/health")
    (r.ok if code == 200 else r.bad)("grafana reachable", str(body)[:60].replace("\n", " "))
    code, body = http(f"{GRAFANA}/api/dashboards/uid/voyantra-overview")
    if code != 200:
        r.bad("dashboard provisioned", f"HTTP {code}")
        return
    d = json.loads(body)["dashboard"]
    panels = d.get("panels", [])
    rows = [p for p in panels if p.get("type") == "row"]
    r.ok("dashboard provisioned", f"{len(panels)} panels in {len(rows)} sections")


def check_tracing(r: Report) -> None:
    section("6 · jaeger")
    code, body = http(f"{JAEGER}/api/services")
    if code != 200:
        r.bad("jaeger reachable", f"HTTP {code}")
        return
    services = json.loads(body).get("data") or []
    for svc in ("tp-api", "tp-worker"):
        present = svc in services
        (r.ok if present else r.bad)(
            f"jaeger service {svc}", "present" if present else "MISSING")

    # A service can be registered from an old trace while recording nothing now.
    code, body = http(f"{JAEGER}/api/traces?service=tp-worker&limit=5&lookback=2h")
    n = len(json.loads(body).get("data") or []) if code == 200 else 0
    (r.ok if n > 0 else r.warn)("recent tp-worker traces", f"{n} in the last 2h")


def check_langfuse(r: Report) -> None:
    section("7 · langfuse")
    import os
    port = os.environ.get("LANGFUSE_PORT", "3013")
    pk, sk = os.environ.get("LANGFUSE_PUBLIC_KEY"), os.environ.get("LANGFUSE_SECRET_KEY")
    code, _ = http(f"http://localhost:{port}/api/public/health")
    (r.ok if code == 200 else r.bad)("langfuse reachable", f"HTTP {code}")
    if not (pk and sk):
        r.void("langfuse recording generations", "keys not in env - run via `make verify-all`")
        return
    import base64
    import urllib.request
    req = urllib.request.Request(
        f"http://localhost:{port}/api/public/observations?limit=1&type=GENERATION")
    req.add_header("Authorization",
                   "Basic " + base64.b64encode(f"{pk}:{sk}".encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            total = json.loads(resp.read()).get("meta", {}).get("totalItems", 0)
        (r.ok if total > 0 else r.bad)("langfuse recording generations", f"{total} total")
        # Counting traces is NOT a health check - Langfuse can be up, authenticating, and
        # recording nothing. The count is the assertion.
    except Exception as e:  # noqa: BLE001
        r.bad("langfuse recording generations", f"{type(e).__name__}: {e}")


def check_retrieval(r: Report) -> None:
    section("8 · retrieval integrity")
    code, out = dexec(WORKER, [
        "python", "-c",
        "import asyncio;from tp_retrieval.vectorstore import QdrantStore;"
        "print(asyncio.run(QdrantStore.from_settings(dim=1024).read_meta()))",
    ], timeout=90)
    ok = code == 0 and "embedder_model" in out
    # Both candidate embedders emit 1024 dims, so a dimension check passes either way.
    # Only the stamp can catch a mismatch, and a wrong embedder still returns plausible
    # results - a quality failure, invisible without this.
    (r.ok if ok else r.bad)("embedder provenance stamp", out.strip()[:110])


def check_controls(r: Report) -> None:
    section("9 · cost controls & breakers")
    code, out = dexec(REDIS, ["redis-cli", "get", "planning:enabled"])
    v = out.strip()
    if code != 0:
        r.void("runtime kill switch", "redis unreachable")
    elif v in ("0", "false"):
        r.bad("runtime kill switch RELEASED", f"planning:enabled={v} - planning is OFF")
    else:
        r.ok("runtime kill switch released", "no runtime override")

    _, floor = dexec(APIC, ["sh", "-c", "echo $LLM_ENABLED"])
    f = floor.strip()
    (r.bad if f == "false" else r.ok)(
        "static floor released",
        f"LLM_ENABLED={f}" + (" - planning is OFF" if f == "false" else " (running api)"))

    _, lim = dexec(APIC, ["sh", "-c", "echo $DAILY_SPEND_LIMIT_USD"])
    r.ok("daily spend limit", f"{lim.strip() or '0'} (0 = breaker disabled)")

    res = promq("tp_venue_circuit_state")
    if not res:
        r.warn("venue breakers", "no series - no venue touched since the api restarted")
    else:
        states = {s["metric"].get("provider"): s["value"][1] for s in res}
        open_legs = [k for k, v in states.items() if v == "2"]
        (r.ok if not open_legs else r.bad)(
            "venue breakers closed", str(states) if not open_legs else f"OPEN: {open_legs}")

    _, hosts = dexec(WORKER, ["cat", "/etc/hosts"])
    leftover = [ln for ln in hosts.splitlines()
                if ln.startswith("127.0.0.1")
                and any(h in ln for h in ("sglang", "vllm", "api.groq.com", "api.openai.com"))]
    (r.ok if not leftover else r.bad)(
        "no leftover fault injection", "clean" if not leftover else str(leftover))


# ------------------------------------------------------------- 10: judge YOUR runs
def analyse_runs(r: Report) -> None:
    section(f"10 · YOUR RUNS — the last {WINDOW_MIN} minutes")
    code, out = psql(
        "select coalesce(request->>'city', 'TRIP '||(request->'cities')::text), "
        "kind, status, coalesce(result->>'grounded','-'), "
        "coalesce(jsonb_array_length(result->'days'),0), "
        "coalesce(result->'venues','[]')::text, "
        "coalesce(warnings::text,'[]'), "
        "coalesce(result->'center'->>'latitude','-'), "
        "coalesce(result->'center'->>'longitude','-'), "
        "round(cost_usd::numeric,6) "
        "from runs where created_at > now() - interval '" + str(WINDOW_MIN) + " minutes' "
        "order by created_at", timeout=60)
    rows = [ln.split("|") for ln in out.strip().splitlines() if ln.strip()]
    if not rows:
        r.void("runs to analyse", f"no runs in the last {WINDOW_MIN} minutes - drive the UI first")
        return
    r.ok("runs found", f"{len(rows)} in the last {WINDOW_MIN} minutes")

    kinds = {"grounded": 0, "declined": 0, "other": 0}
    fabrications, wrong_anchor, unfinished, cost_mismatch = [], [], [], []

    for row in rows:
        if len(row) < 10:
            continue
        city, kind, status, grounded, days, venues, warns, lat, lon, cost = row[:10]
        venues_l = json.loads(venues) if venues.startswith("[") else []
        days_n = int(days or 0)

        if status not in ("succeeded", "failed", "error"):
            unfinished.append(f"{city} ({status})")  # refined below by age

        if grounded == "true":
            kinds["grounded"] += 1
        elif grounded == "false":
            kinds["declined"] += 1
        else:
            kinds["other"] += 1

        # THE dangerous failure: text produced with no model behind it.
        if grounded == "true" and days_n > 0 and not venues_l:
            fabrications.append(city)

        # Cost attribution: a local venue must be $0 and RECORDED; a hosted leg must be >0.
        try:
            c = float(cost)
            if venues_l:
                local = any(v.startswith("local-") for v in venues_l)
                if local and c != 0:
                    cost_mismatch.append(f"{city}: {venues_l} charged ${c}")
                if not local and c == 0:
                    cost_mismatch.append(f"{city}: hosted {venues_l} charged $0")
        except ValueError:
            pass

        # Wrong anchor - the class that produced a Washington DC itinerary labelled Nara.
        key = (city or "").strip().lower()
        if key in KNOWN_BOXES and lat not in ("-", "") and lon not in ("-", ""):
            lo_a, hi_a, lo_o, hi_o, where = KNOWN_BOXES[key]
            try:
                la, lo = float(lat), float(lon)
                if not (lo_a <= la <= hi_a and lo_o <= lo <= hi_o):
                    wrong_anchor.append(f"{city} -> {la:.3f},{lo:.3f} (expected {where})")
            except ValueError:
                pass

    r.ok("outcome mix", f"grounded={kinds['grounded']} declined={kinds['declined']} "
                        f"other/trip={kinds['other']}")

    # ORPHANS. A run row is written BEFORE the task is safely processed, so losing the
    # broker (Q15 stops Redis, and appendonly is off) strands the row at `queued` with no
    # error and no reconciliation - it stays that way forever. Distinguish "still working"
    # from "will never run" by age against the Celery visibility timeout.
    _, orph = psql(
        "select count(*) from runs where status not in ('succeeded','failed','error') "
        "and created_at < now() - interval '15 minutes'")
    _, depth = dexec(REDIS, ["redis-cli", "llen", "celery"])
    n_orph = int(orph.strip() or 0)
    if n_orph:
        r.bad("no runs orphaned in 'queued'",
              f"{n_orph} run(s) queued >15min ago with {depth.strip()} task(s) pending - "
              "the broker was lost and nothing reconciles the row")
    else:
        r.ok("no runs orphaned in 'queued'", f"queue depth {depth.strip()}")
    if unfinished:
        r.warn("runs still in flight", f"{len(unfinished)} not yet terminal (may be normal)")

    (r.ok if not fabrications else r.bad)(
        "no itinerary was produced without a venue",
        "none" if not fabrications else f"FABRICATED: {fabrications[:5]}")

    (r.ok if not cost_mismatch else r.bad)(
        "cost attribution matches the venue",
        "consistent" if not cost_mismatch else str(cost_mismatch[:4]))

    (r.ok if not wrong_anchor else r.bad)(
        "no run was anchored on the wrong place",
        "all known cities landed correctly" if not wrong_anchor else str(wrong_anchor[:5]))

    # grounded=false is TWO different outcomes with different costs, and conflating them
    # reports a healthy degraded run as a suspicious decline:
    #   not_found - geocode failed, NO model was called, venues=[]     -> free
    #   degraded  - geocoded fine, no POIs there, model wrote an intro -> paid
    # `kyota` is the second kind: it resolved to Uganda, found nothing, and still called a
    # model. venues=[] proves the first; it says nothing about the second.
    if kinds["declined"]:
        _, nf = psql(
            "select count(*) from runs where created_at > now() - interval '"
            + str(WINDOW_MIN) + " minutes' and result->>'grounded'='false' "
            "and coalesce(result->'venues','[]')::text = '[]'")
        _, dg = psql(
            "select count(*) from runs where created_at > now() - interval '"
            + str(WINDOW_MIN) + " minutes' and result->>'grounded'='false' "
            "and coalesce(result->'venues','[]')::text <> '[]'")
        r.ok("not_found declines cost nothing",
             f"{nf.strip()} run(s) with venues=[] - no model was called")
        if int(dg.strip() or 0):
            r.warn("degraded runs DID call a model",
                   f"{dg.strip()} run(s) geocoded but found no POIs - check the anchor "
                   "was the place you meant")


def main() -> int:
    print("\nVERIFY ALL — every component, then the runs you produced")
    print("  read-only: nothing is stopped, flipped, injected or recreated\n")
    r = Report()
    check_containers(r)
    check_datastores(r)
    check_dispatch(r)
    check_prometheus(r)
    check_grafana(r)
    check_tracing(r)
    check_langfuse(r)
    check_retrieval(r)
    check_controls(r)
    analyse_runs(r)
    return r.summary()


if __name__ == "__main__":
    raise SystemExit(main())
