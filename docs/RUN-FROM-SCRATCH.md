# 🚀 Run Voyantra From Scratch

The exact command sequence to bring the app up on a clean machine — **which
component starts first, second, third, and why**. Everything is driven through the
`Makefile`; you never call `docker compose -f …` by hand.

> **In a hurry?** One command does the whole "from scratch" path:
> ```bash
> make bootstrap
> ```
> The rest of this doc explains what that command does, and how to run each step
> by hand if you want to.

---

## 0. Prerequisites (once per machine)

| Need | Why |
|---|---|
| **Docker Desktop** running | every component is a container |
| **`.env`** at the repo root | ports + secrets (copy from `.env.example`, set `OPENAI_API_KEY`) |
| `uv` (Python 3.13) | only for the host-side `make migrate` / `make seed` steps |

```bash
cp .env.example .env        # then edit: set OPENAI_API_KEY=sk-...
```

`OPENAI_API_KEY` is the only **required** value — the app fails fast at startup
without it. Everything else has a safe default.

---

## 1. Startup order — what runs before what

Components must come up in dependency order. The Makefile encodes this; here it is
explicitly, with the host port each one listens on (see [§4](#4-port-map)):

```
TIER 1 — DATA (stateful stores, start first)
  1. Postgres   :3001   run-state + LangGraph checkpoints
  2. Redis      :3002   Celery broker + cache + SSE pub/sub
  3. Qdrant     :3003   vector DB (POI corpus for RAG)
        │  (api/worker wait for these to be healthy)
        ▼
TIER 2 — APP (starts after data is healthy)
  4. API        :3004   FastAPI — creates the DB schema on boot, dispatches work
  5. Worker     :3005   Celery worker (runs the LangGraph agent); metrics port
  6. Web        :3006   Next.js UI (waits for the API to be healthy)
        │
        ▼
TIER 3 — OBSERVABILITY (optional; start any time after the app)
  7. Jaeger     :3007   ·  OTLP receiver :3008
  9. Prometheus :3009   · Grafana :3010 · Flower :3011 · RedisInsight :3012
 13. Langfuse   :3013   ·  MinIO console :3014
```

**Why this order:** the API and worker open connections to Postgres/Redis/Qdrant
the moment they start, so the data stores must be accepting connections first. The
web UI proxies to the API, so it comes up last. Observability only *reads* from the
others (scrapes metrics, receives traces), so it can start whenever.

The Makefile enforces tiers 1→2 with `--wait` (it blocks until each store reports
healthy before starting the app). You don't have to time anything yourself.

---

## 2. The one-command path

```bash
make bootstrap
```

That target runs, in order:

1. `docker compose -f data -f app up --build -d --wait`
   — builds + starts **data tier**, waits until Postgres/Redis/Qdrant are healthy,
   then starts the **app tier** and waits until the API is healthy.
2. `make migrate` — creates the Postgres schema (idempotent; see note below).
3. `make seed` — ingests the POI corpus into Qdrant.
4. `make urls` — prints every URL.

When it finishes, the app is fully usable at **http://localhost:3006** (login
password `voyantra`). To add the dashboards, follow with `make full`.

> **About "migrations":** this repo doesn't use Alembic yet — the schema is built by
> an idempotent `create_all` (`init_models()`), and the API/worker already run it on
> boot. `make migrate` just runs the same thing explicitly so the step is visible and
> re-runnable. (Alembic is planned for the auth milestone, at which point `make
> migrate` becomes `alembic upgrade head` and nothing else changes.)

---

## 3. The same thing, step by step (manual)

Run these in order if you'd rather drive each tier yourself:

```bash
# 1. DATA — Postgres + Redis + Qdrant (wait until healthy)
make data

# 2. APP  — api + worker + web (builds images on first run; the API creates the schema)
make app

# 3. SCHEMA — explicit, idempotent (the app already did this on boot; safe to repeat)
make migrate

# 4. SEED — load the POI corpus into Qdrant (one-time; persists in the tp_qdrant volume)
make seed

# 5. (optional) OBSERVABILITY — dashboards + Langfuse
make observability     # or: `make full` to (re)assert data+app+observability together

# 6. See where everything lives
make urls
```

Check health at any point:

```bash
make ps
```

> ⚠️ **Seed with one embedder.** `make seed` forces OpenAI embeddings
> (`VOYAGE_API_KEY=` empty) so the index and the worker's query embedder share one
> vector space. Mixing embedders makes retrieval silently return nothing and the plan
> degrades to live web POIs with no error.

---

## 4. Port map

Ports are **sequenced by startup order** and all live in the 3000 range, set in
`.env` (override any of them there — the compose files and `make urls` read `.env`).

| # | Component | Tier | `.env` var | Host port |
|---|---|---|---|---|
| 1 | Postgres | data | `POSTGRES_PORT` | 3001 |
| 2 | Redis | data | `REDIS_PORT` | 3002 |
| 3 | Qdrant | data | `QDRANT_PORT` | 3003 |
| 4 | API (backend) | app | `API_PORT` | 3004 |
| 5 | Worker metrics | app | `WORKER_METRICS_PORT` | 3005 (in-network only) |
| 6 | Web (frontend) | app | `WEB_PORT` | 3006 |
| 7 | Jaeger UI | obs | `JAEGER_UI_PORT` | 3007 |
| 8 | OTLP/HTTP receiver | obs | `OTLP_HTTP_PORT` | 3008 |
| 9 | Prometheus | obs | `PROMETHEUS_PORT` | 3009 |
| 10 | Grafana | obs | `GRAFANA_PORT` | 3010 |
| 11 | Flower | obs | `FLOWER_PORT` | 3011 |
| 12 | RedisInsight | obs | `REDISINSIGHT_PORT` | 3012 |
| 13 | Langfuse | obs | `LANGFUSE_PORT` | 3013 |
| 14 | MinIO console | obs | `MINIO_CONSOLE_PORT` | 3014 |

> These are **host** ports only. Inside the compose network, containers still talk to
> each other on their conventional ports (`db:5432`, `redis:6379`, `qdrant:6333`,
> `api:8000`, …). So changing a host port in `.env` never breaks container-to-container
> traffic. Two sync points are kept in lockstep with `.env`: `DATABASE_URL`/`REDIS_URL`
> (host connection strings) and `infra/observability/prometheus.yml` (scrapes
> `worker:3005`).

---

## 5. Tear down / start over

```bash
make down      # stop everything, KEEP data (Postgres + Qdrant volumes survive)
make downv     # stop everything AND wipe all volumes (truly from scratch next time)
```

After `make downv`, the next `make bootstrap` rebuilds the schema and re-seeds the
corpus automatically.

---

## 6. Make command reference

| Command | Tier(s) | What it does |
|---|---|---|
| `make bootstrap` | data + app | **From scratch in one shot:** stores → schema → app → seed |
| `make data` | data | Postgres + Redis + Qdrant only |
| `make app` | data + app | data + api/worker/web |
| `make observability` | obs | dashboards + Langfuse (standalone) |
| `make full` | all | data + app + observability together |
| `make migrate` | — | create/upgrade the Postgres schema (idempotent) |
| `make seed` | — | ingest the POI corpus into the running Qdrant |
| `make urls` | — | print which URL opens which UI |
| `make ps` / `make logs` | — | status / tail logs for the whole stack |
| `make down` / `make downv` | — | stop (keep / wipe data) |
