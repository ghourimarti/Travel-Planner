# 🧭 Voyantra — Local Runbook (Run Everything + See Every Metric)

A copy-paste guide to bring the **whole system** up locally in Docker and view every
component on a web UI: the app, the agent traces, metrics dashboards, the queue, the
cache, the vector DB, and the kill-switch.

> **First time / clean machine?** See **[RUN-FROM-SCRATCH.md](RUN-FROM-SCRATCH.md)** for
> the exact startup order and the one-command path (`make bootstrap`). That doc is the
> canonical source for the **port map** — host ports are now sequenced **3001–3014** in
> `.env`; `make urls` always prints the live values.

> **TL;DR** — pick a tier, then `make urls` prints where to click.
> ```bash
> make bootstrap       # from scratch: data + app + schema + seeded corpus
> make full            # add the observability dashboards (incl. self-hosted Langfuse)
> make urls            # print which URL opens which UI
> ```

---

## 1. What you get (10 containers)

Yes — **every dashboard below is a Docker container**, started by the three compose files.

| Container | Image | Role | Web UI |
|---|---|---|---|
| `web` | (built) | Next.js app (plan form, live trace, MapLibre map) | **http://localhost:3000** |
| `api` | (built) | FastAPI — dispatch, SSE, `/metrics`, `/docs` | **http://localhost:8000/docs** |
| `worker` | (built) | Celery worker running the LangGraph multi-agent | (no UI; metrics on :9200) |
| `db` | postgres:16 | Run-state store + LangGraph checkpoints | (use a DB client on :5432) |
| `redis` | redis:7 | Celery broker + cache + SSE pub/sub | via RedisInsight |
| `qdrant` | qdrant/qdrant | Vector DB (POI corpus, RAG) | **http://localhost:6333/dashboard** |
| `jaeger` | jaegertracing/all-in-one | Distributed **traces** (api→worker→agent→llm) | **http://localhost:16686** |
| `grafana` | grafana/grafana | **Metrics dashboards** (PromQL) | **http://localhost:3001** |
| `prometheus` | prom/prometheus | Scrapes app metrics, stores time-series | **http://localhost:9090** |
| `flower` | mher/flower | **Celery** task/worker monitor | **http://localhost:5555** |
| `redisinsight` | redis/redisinsight | **Redis** browser (queue, cache, kill-switch) | **http://localhost:5540** |

**Three** compose files layer into tiers (drive them with the Makefile, not raw `-f` flags):
- `docker-compose.data.yml` — data stores (`db`, `redis`, `qdrant`) → `make data`
- `docker-compose.app.yml` — the app (`api`, `worker`, `web`); also wires the OTLP/Langfuse
  trace export into `api`/`worker` (best-effort — harmless when the obs tier isn't running) → `make app`
- `docker-compose.observability.yml` — dashboards (`jaeger`, `grafana`, `prometheus`, `flower`,
  `redisinsight`) **and** self-hosted **Langfuse** + its ClickHouse/MinIO/Postgres/Redis → `make observability`

Make commands: `make data` · `make app` · `make observability` · `make full` (= data + app + observability) · `make bootstrap` (from-scratch app + seed).

> ℹ️ The port column above shows the **old** defaults. Host ports were renumbered to a
> sequenced 3001–3014 scheme — run `make urls` (or see [RUN-FROM-SCRATCH.md](RUN-FROM-SCRATCH.md) §4) for current values.

---

## 2. Prerequisites
- Docker Desktop running.
- `.env` at the repo root with **`OPENAI_API_KEY=sk-...`** (required; the app fails fast without it).
- (For the eval harness / native dev) Python 3.13 + `uv`.

---

## 3. Bring it all up

```bash
cd "<repo root>"
make observability   # data + app + dashboards (or `make full` to add Langfuse)
```

First run builds the `api`/`worker`/`web` images (a few minutes). Check health:

```bash
make ps
```

> Want fewer pieces? `make data` (just the stores) or `make app` (stores + app, no dashboards).

All app services should read `healthy`.

### 3a. One-time: load the POI corpus into Qdrant
The vector DB starts empty. Ingest the curated corpus **once** (it persists in the
`tp_qdrant` volume across restarts). Use the keyless-OpenAI override so the index and
the worker's query embedder share one vector space:

```bash
make seed
# -> "Ingested 25 POIs into Qdrant."
```
`make seed` runs the ingest against the running Qdrant server with a single consistent
(OpenAI) embedder — see the warning below for why that matters.

Verify: `curl -s localhost:6333/collections/pois | grep -o '"points_count":[0-9]*'`

> ⚠️ **Why the override matters:** if you ingest with one embedder (e.g. Voyage) and the
> worker queries with another (OpenAI), retrieval silently returns nothing and the plan
> degrades to live web POIs with **no error**. Keep ingest + query on the same embedder.

---

## 4. Generate some traffic (so the dashboards have data)

```bash
# single city
curl -s -X POST localhost:8000/plan -H "content-type: application/json" \
  -d '{"city":"Kyoto","interests":["temples","food"],"days":1}'

# multi-city trip
curl -s -X POST localhost:8000/trip -H "content-type: application/json" \
  -d '{"cities":["Paris","Rome"],"interests":["history","food"],"days":2}'
```

Each returns `{"run_id": "...", "status": "queued"}`. Re-run a few times to populate
metrics/traces.

---

## 5. See everything — UI by UI

### 🗺️ The app — http://localhost:3000
1. Log in with the dev password **`voyantra`**.
2. Enter a city/cities + interests → **Plan**.
3. Watch the **live trace timeline** (geocode → gather → compose → critic → done) and the
   grounded POIs drop onto the **MapLibre map**.

### 🔍 Jaeger — distributed traces — http://localhost:16686
The "one run = one trace" engineering view.
1. **Service** → `tp-worker` → **Find Traces**.
2. Click a trace → waterfall of spans:
   `POST /plan` → `run/plan_task` → `agent.gather/compose/critic` → `llm.complete`.
3. Click an `llm.complete` span → attributes show **tier, model, tokens, cost_usd**
   (never prompt text). Bar length = latency (find the slow span).
4. **Live:** fire a plan, click **Find Traces** again — new trace appears in seconds.

### 📊 Grafana — metrics dashboards — http://localhost:3001
Anonymous admin (no login). Go to **Explore** (compass icon) → datasource **Prometheus**
→ paste a query → set auto-refresh (top-right) to **5s** to watch it live:

| Query | Shows |
|---|---|
| `rate(tp_runs_total[5m])` | run throughput by terminal status (succeeded/failed) |
| `tp_run_cost_usd_sum / tp_run_cost_usd_count` | **mean cost / itinerary** vs the $0.30 cap |
| `tp_llm_calls_total` | LLM calls (by tier/model/provider → **tiering + fallback**) |
| `tp_critic_revisions_total` | critic-triggered corrective re-composes |
| `histogram_quantile(0.95, rate(tp_run_duration_seconds_bucket[5m]))` | **p95 latency** |
| `tp_dispatch_total` | API dispatch count |

### 📈 Prometheus — raw metrics + scrape health — http://localhost:9090
- **Status → Targets**: `tp-api` and `tp-worker` should be **UP**.
- **Graph** tab: type any `tp_*` metric (e.g. `tp_run_cost_usd_sum`) and Execute.

### 🌸 Flower — Celery tasks — http://localhost:5555
- **Tasks** tab: each plan/trip is a task; watch states flip `RECEIVED → STARTED → SUCCESS`
  (failures + retries show here too).
- **Workers** tab: the live worker pool and concurrency.

### 🧱 RedisInsight — queue, cache, kill-switch — http://localhost:5540
1. **Add Redis database** → Host `redis`, Port `6379` (no password) → Add.
2. **Browser** → watch keys appear:
   - `celery` — the broker queue.
   - `geo:* pois:* wx:* route:*` — per-tool **cache** entries (with TTLs).
   - `planning:enabled` — the **kill-switch** key (see the demo below).

### 🧮 Qdrant — vector DB — http://localhost:6333/dashboard
- **Collections → pois** → 25 points. Use **Visualize**/**Console** to inspect vectors and
  payloads (name, category, lat/lon, tenant ACL).

### 🩺 API surface
- **Swagger UI:** http://localhost:8000/docs — try every endpoint interactively.
- **Raw metrics:** http://localhost:8000/metrics — what Prometheus scrapes.
- **Health:** http://localhost:8000/health.

---

## 6. Demos worth running

**Kill-switch (cost/abuse cut-off):**
```bash
docker exec p3-ai-travel-planner-redis-1 redis-cli set planning:enabled 0   # turn planning OFF
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/plan \
  -H "content-type: application/json" -d '{"city":"Kyoto","interests":["food"],"days":1}'   # -> 503
docker exec p3-ai-travel-planner-redis-1 redis-cli del planning:enabled     # back ON (fail-open)
```

**Caching:** run the same city twice — the second run's `geo:*`/`pois:*` keys are already
present in RedisInsight, and tool spans in Jaeger get faster.

**Partial results (resilience):** request a real city + a nonsense one in `/trip`
(`["Paris","asdfqwer"]`) — the trip still succeeds with the bad city flagged, visible as a
`failed`-tagged event and in the result's `failed` list.

---

## 7. The things that have NO web UI (run these instead)

| Capability | How to see it |
|---|---|
| ACL-at-retrieval · PII redaction · prompt-injection | `uv run pytest -k "acl or tenant or redact or pii or inject" -v` |
| RAGAS / LLM-judge / eval quality | `QDRANT_URL=http://localhost:6333 VOYAGE_API_KEY= uv run python -m tp_eval --judge gateway --retrieve` |
| Circuit breakers / retries / backpressure | `make chaos` (kills LLM/Redis/Qdrant, asserts graceful degradation) |
| Full quality gate | `make check` (lint + strict types + tests) |

> **Deploy-only UIs:** GitHub Actions (`github.com/<repo>/actions`, after you push) and
> ArgoCD + Argo Rollouts (need a kind/EKS cluster — `bash scripts/kind-up.sh`). Langfuse
> (LLM-native trace UI) needs its own heavier stack and is not in this overlay.

---

## 8. Stop / clean up

```bash
make down     # stop, keep data (Postgres + Qdrant volumes survive)
make downv    # stop AND wipe all data volumes
```

---

## 9. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Dashboards gone after a while | If the host slept/restarted, non-app containers exit. Re-run the `up -d` command in §3. |
| Plan succeeds but POIs look like odd Wikipedia articles | Empty/mismatched Qdrant. Re-run the ingest in §3a (same embedder!). |
| No traces in Jaeger | You started without the **third** compose file — traces only export with `docker-compose.observability.yml` included. |
| Grafana panels empty | No traffic yet — run §4; ensure Prometheus targets are UP (§5). |
| `POST /plan` returns 503 | Kill-switch is on — `docker exec p3-ai-travel-planner-redis-1 redis-cli del planning:enabled`. |
| Port already in use (5540, etc.) | A stray old container holds the port — `docker rm -f <name>`. |
