<div align="center">

<img src="https://img.shields.io/badge/Jillani%20SofTech-Enterprise%20AI-1d6fe0?style=for-the-badge&logo=brain&logoColor=white" />

# 🧭 Voyantra — AI Travel Planner

### Multi-Agent, Multi-City Itinerary Intelligence — Grounded in Real Places, Weather & Routing

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-1C3C3C?style=flat-square&logo=langchain&logoColor=white)](#-how-the-agentic-rag-pipeline-works)
[![OpenAI](https://img.shields.io/badge/OpenAI-Tiered%20%2B%20Fallback-412991?style=flat-square&logo=openai&logoColor=white)](https://openai.com)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20RAG-DC244C?style=flat-square&logo=qdrant&logoColor=white)](https://qdrant.tech)
[![Celery](https://img.shields.io/badge/Celery-Redis-37814A?style=flat-square&logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Postgres](https://img.shields.io/badge/Postgres-Run%20State-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Auth0](https://img.shields.io/badge/Auth-Auth0%20JWT-EB5424?style=flat-square&logo=auth0&logoColor=white)](#-security)
[![Next.js](https://img.shields.io/badge/Next.js-15%20%2F%20React%2019-000000?style=flat-square&logo=nextdotjs&logoColor=white)](https://nextjs.org)
[![Observability](https://img.shields.io/badge/OTel%20%2B%20Langfuse%20%2B%20Prometheus-Tracing-F46800?style=flat-square&logo=opentelemetry&logoColor=white)](#-observability)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![Kubernetes](https://img.shields.io/badge/K8s-kind%20%E2%86%92%20EKS-326CE5?style=flat-square&logo=kubernetes&logoColor=white)](#-deployment)
[![Terraform](https://img.shields.io/badge/Terraform-EKS%2FRDS%2FECR-7B42BC?style=flat-square&logo=terraform&logoColor=white)](#-deployment)


[🚀 Quick Start](#-quick-start) · [✨ Features](#-features) · [🏗️ Architecture](#-architecture) · [📡 API](#-api-reference) · [🐳 Deployment](#-deployment)


</div>

---

## 📌 What Is This?

**Voyantra** is a full-stack, production-grade **Agentic RAG** travel planner. You give it one to five cities, your interests, and a trip length — and a **multi-agent system** plans each city *in parallel*, grounds every recommendation in **real places** (a curated POI corpus + live geo/weather/routing data), sequences a feasible day-by-day plan, computes inter-city travel legs, and a **critic agent** verifies the draft for invented places and infeasible timing before it ships. You watch the whole thing happen **live** and see it on a map.

It started life as a bootcamp Streamlit demo — one LLM call that *hallucinated* attractions, with no tests, no API, and no resilience. It was rebuilt, decision by decision, into a deployable service.

> ⚠️ **Not a toy demo.** Tiered LLM gateway with cross-provider fallback, real vector RAG over Qdrant, async dispatch on Celery + Postgres with **resume-after-crash**, live SSE streaming, Auth0 JWT with per-tenant data isolation, an **eval gate** in CI, full OpenTelemetry/Langfuse/Prometheus observability, multi-stage Docker, a Helm chart on Kubernetes, and Terraform for EKS — **142 tests, strict typing, 0 CVEs.**

---

## ✨ Features

| Feature | Description |
|---|---|
| 🧠 **Multi-Agent Planner** | A coordinator fans out one **worker agent per city** (parallel) + a **critic agent** that catches invented places and re-plans (capped corrective loop) |
| 🗺️ **Real-Place Grounding** | Itineraries are grounded in a curated POI corpus (Qdrant RAG) + live geocoding/POI/weather/routing — **it refuses to invent** when it can't ground |
| 🌍 **Multi-City Trips** | 1–5 cities, up to 10 days, **parallel fan-out**, inter-city travel legs, and **partial results** (one city fails, the rest still ship) |
| ⚡ **Async + Resumable** | `POST` returns a `run_id` instantly; the worker runs the graph; a crashed worker **resumes from the last completed node** (LangGraph Postgres checkpointer) |
| 📡 **Live Trace Streaming** | Server-Sent Events stream each agent step (geocode → gather → compose → critic) to the browser in real time |
| 🔀 **Tiered LLM Gateway** | `gpt-4o-mini` → `gpt-4o` by step difficulty, with **cross-provider fallback** (OpenAI → Anthropic → Groq, key-gated) for outage resilience |
| 💰 **Cost-Bounded** | Per-run **and per-sub-agent** hard caps + a global kill switch + a budget eval gate — real cost **~$0.002–0.007/itinerary** (≤ $0.30 ceiling) |
| 🔐 **Enterprise Security** | Auth0 JWT (fail-closed) · per-tenant run isolation · **ACL enforced inside Qdrant** · PII log redaction · prompt-injection guard · rate limiting |
| 📈 **Full Observability** | One run = one OpenTelemetry trace (api→worker→agent→llm) · Langfuse generations · Prometheus RED + cost metrics — **no prompt text ever logged** |
| 🐳 **Deploy-Ready** | Multi-stage non-root Docker · Helm chart (kind→EKS) · Terraform (EKS/RDS/ElastiCache/ECR/IRSA) · ArgoCD GitOps · CI with an eval gate |

---

## 🖼️ Screenshots

<div align="center">

### Marketing Site (Next.js)
![Landing Page](screenshots/landing.png)

### Plan Form + Live Agent Trace
![Live Trace](screenshots/app_run_trace.png)

### Grounded Itinerary on the Map (MapLibre)
![Map View](screenshots/map_view.png)

</div>

> _Add real captures to `screenshots/` — the front end (`apps/web`) renders the marketing site, the product dashboard, the live trace timeline, and the MapLibre map._

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│             CLIENT  ·  Next.js 15 / React 19 / Tailwind          │
│        Marketing site · Product app · Live trace · MapLibre      │
│   same-origin BFF route handlers attach the Auth0 token server-  │
│   side  →  the access token never reaches the browser            │
└─────────────────────────┬────────────────────────────────────────┘
                          │  REST + SSE (EventSource)
┌─────────────────────────▼────────────────────────────────────────┐
│                  FastAPI  Backend  (async, Port 8000)            │
│  POST /plan  POST /trip → persist Run + enqueue → 202 {run_id}   │
│  GET /runs/{id}   GET /runs/{id}/stream (SSE)   /health /metrics │
│  Auth0 JWT (fail-closed) · per-tenant rate-limit · kill switch   │
└──────┬───────────────────┬─────────────────────┬─────────────────┘
       │                   │                     │
┌──────▼──────┐   ┌────────▼────────┐   ┌────────▼─────────┐
│  Postgres   │   │  Celery + Redis │   │   Redis caches   │
│  run state  │   │   broker/queue  │   │ geo/POI/weather/ │
│  + audit    │   └────────┬────────┘   │ route (per-TTL)  │
│ (tenant-    │            │            └──────────────────┘
│  scoped)    │   ┌────────▼─────────────────────────────────┐
└─────────────┘   │   WORKER · LangGraph multi-agent         │
                  │   coordinator                            │
┌─────────────┐   │    └─ per-city worker  (parallel)        │
│   Qdrant    │◄──┤        geocode → gather → compose        │
│  POI vectors│   │        (corpus RAG + live tools)         │
│ ~1024-d,ACL │   │    → critic → corrective loop            │
└─────────────┘   │    → merge + inter-city legs             │
                  └────────┬─────────────────────────────────┘
┌─────────────────────────▼─────────────────────────────────┐
│   LLM gateway · tier gpt-4o-mini→gpt-4o · fallback         │
│   OpenAI → Anthropic → Groq (key-gated) · per-call cost    │
└───────────────────────────────────────────────────────────┘
  Observability: OpenTelemetry trace · Langfuse · Prometheus
  Durability: LangGraph Postgres checkpointer (resume-after-crash)
```

### Request Flow

```
[Traveler]
   │  enter cities + interests + days  (Auth0 session)
   ▼
POST /plan|/trip ──► persist Run (tenant-scoped) ──► enqueue Celery task ──► 202 {run_id}
   │
   ├──► GET  /runs/{id}          ──►  status: queued | running | succeeded | failed (+ result)
   └──► GET  /runs/{id}/stream   ──►  SSE: geocode → gather → compose → critic → done
                                       │
        WORKER (LangGraph)  ──────────►  per-city: geocode → retrieve real POIs (Qdrant + live tools)
                                          → weather → compose day plan → CRITIC checks grounding
                                          → (revise if needed) → merge cities + inter-city legs
                                          → record status/result/cost on the Run
```

---

## 🗂️ Project Structure

```
voyantra-ai-travel-planner/            # uv monorepo (workspace)
├── packages/
│   ├── core/      tp_core              # config · JSON logging · exceptions · LLM gateway
│   │                                   # cache · cost cap/kill-switch · auth · tracing · metrics · guard · ratelimit
│   ├── tools/     tp_tools             # geocode / POI / weather / routing  (keyless OSS + resilient HTTP)
│   ├── agents/    tp_agents            # LangGraph multi-agent graph · coordinator · critic · checkpointer
│   ├── retrieval/ tp_retrieval         # embeddings · Qdrant store (tenant ACL) · hybrid retrieve · rerank · ingest
│   └── eval/      tp_eval              # golden set · metrics · LLM-judge · CI eval GATE
├── apps/
│   ├── api/       tp_api               # FastAPI: async dispatch · SSE · Auth0 · /metrics · RTBF
│   ├── worker/    tp_worker            # Celery worker that runs the planner graph
│   └── web/       voyantra-web         # Next.js 15 · BFF · live trace UI · MapLibre map · Auth0/dev-login
├── infra/
│   ├── helm/voyantra/                  # single Helm chart (kind & EKS; managed-DB toggles)
│   ├── kind/                           # local kind cluster config
│   ├── terraform/                      # EKS · RDS · ElastiCache · ECR · IRSA · VPC
│   ├── argocd/                         # AppProject + dev/staging/prod Applications
│   └── observability/alerts.yaml       # Prometheus alert rules (cost/SLO)
├── tests/load/plan_smoke.js            # k6 load test (ramps to 50 concurrent)
├── scripts/backup_restore_drill.sh     # pg_dump → restore-verify → row-count compare
├── .github/workflows/                  # ci.yml (gate + audits) · cd.yml · promote.yml (eval gate)
├── docs/                               # architecture-decision-log · decision-summary · runbook
│                                       # production-hardening · case-study
├── data/corpus/pois.jsonl              # seed POI corpus
├── docker-compose.yml · docker-compose.app.yml
├── Makefile · pyproject.toml · uv.lock · .env.example
└── demo/                               # original Streamlit demo (legacy; superseded by apps/web)
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| **Agents** | LangGraph (coordinator + per-city worker + critic, corrective loop) |
| **LLM** | OpenAI `gpt-4o-mini` (cheap) / `gpt-4o` (mid+frontier) via a tiered gateway; fallback OpenAI → Anthropic → Groq |
| **Embeddings** | OpenAI `text-embedding-3-large` @ **1024-d** (Voyage `voyage-3` optional, same dim) |
| **Vector RAG** | Qdrant (embedded-local or server), hybrid + payload filters, **per-tenant ACL** |
| **Tools** | Keyless OSS — Nominatim (geocode) · Overpass / Wikipedia GeoSearch (POI) · Open-Meteo (weather) · OSRM (routing) |
| **Backend** | Python 3.13 · FastAPI (async) · Pydantic v2 |
| **Async** | Celery + Redis broker · Postgres run-state · LangGraph Postgres checkpointer · SSE (Redis pub/sub) |
| **Caching / Cost** | Redis per-tool TTL caches · per-run + per-sub-agent caps · kill switch |
| **Observability** | OpenTelemetry · Langfuse · Prometheus (RED + cost) · structured JSON logs |
| **Security** | Auth0 JWT (fail-closed) · tenant ACL · PII redaction · injection guard · rate limiting |
| **Frontend** | Next.js 15 · React 19 · TypeScript · Tailwind v4 · MapLibre (OpenFreeMap) |
| **Eval** | Custom golden-set metrics + LLM-judge (RAGAS optional) · **blocks CI on regression** |
| **Deployment** | Docker (multi-stage, non-root) · Helm · Kubernetes (kind → EKS) · Terraform · ArgoCD · GitHub Actions |

---

## 🚀 Quick Start

### Prerequisites
- Python **3.13** (pinned in `.python-version`) and [`uv`](https://docs.astral.sh/uv/)
- An **OpenAI API key** (required; the app fails fast without it)
- (Optional) Docker + Docker Compose · Node 22 + pnpm (for the web app)

### Option A — Local Development (no Docker, sqlite default)

```bash
# 1. Clone
git clone https://github.com/jillanisoftech/voyantra-ai-travel-planner.git
cd voyantra-ai-travel-planner

# 2. Install the workspace
uv sync

# 3. Configure
cp .env.example .env                  # set OPENAI_API_KEY (required)

# 4. Quality gate (lint + strict types + 121 tests)
make check

# 5. Build the POI index + score quality
make ingest
make eval-rag                         # -> baselines/baseline-rag.json

# 6. Run the stack (3 shells; omit DATABASE_URL for a zero-Docker sqlite run)
make services                         # Postgres + Redis (Docker)   — optional
make worker                           # Celery worker (runs the graph)
make api                              # uvicorn on :8000
```

Try it:

```bash
curl localhost:8000/health
RID=$(curl -s -X POST localhost:8000/plan -H "content-type: application/json" \
  -d '{"city":"Kyoto","interests":["temples","food"],"days":1}' | jq -r .run_id)
curl -s localhost:8000/runs/$RID            # status + grounded itinerary
curl -N localhost:8000/runs/$RID/stream     # live SSE trace
```

### Option B — Full Container Mesh (Docker)

```bash
docker compose -f docker-compose.yml -f docker-compose.app.yml up --build
# API: http://localhost:8000   ·   Web: http://localhost:3000   ·   Docs: http://localhost:8000/docs
```

### The Web App (Next.js)

```bash
cd apps/web && pnpm install && pnpm dev      # http://localhost:3000  (dev-login fallback when Auth0 is unset)
```

---

## 🔑 Environment Variables

Copy `.env.example` to `.env`. **Only `OPENAI_API_KEY` is required**; everything else has a safe default.

```env
# --- App ---
APP_ENV=local                 # local | dev | staging | prod
LOG_LEVEL=INFO

# --- LLM providers ---
OPENAI_API_KEY=               # REQUIRED (primary; app fails fast if missing)
ANTHROPIC_API_KEY=            # optional fallback rung (inert without a key)
GROQ_API_KEY=                 # optional fallback rung
VOYAGE_API_KEY=               # optional embeddings (voyage-3, same 1024-d)

# --- Persistence / async dispatch ---
DATABASE_URL=postgresql+asyncpg://tp:tp@localhost:5432/tp   # omit → sqlite (zero-Docker dev)
REDIS_URL=redis://localhost:6379/0                          # Celery broker + cache + pub/sub

# --- Vector store ---
QDRANT_URL=                   # set for a Qdrant server; else embedded .qdrant_local/

# --- Cost controls ---
MAX_COST_USD=0.30             # per-itinerary cap + budget eval gate

# --- Observability (optional) ---
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
OTEL_EXPORTER_OTLP_ENDPOINT=  # spans export only when set

# --- Security (Auth0; fail-closed outside local) ---
AUTH_ENABLED=                 # blank → enforced unless APP_ENV=local
AUTH0_DOMAIN=
AUTH0_AUDIENCE=
RATE_LIMIT_PER_MIN=60
```

---

## 📡 API Reference

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | - | Service status |
| `GET` | `/metrics` | - | Prometheus RED + cost metrics |
| `POST` | `/plan` | ✓* | Plan a single city → `202 {run_id}` (async) |
| `POST` | `/trip` | ✓* | Plan a multi-city trip (1–5 cities) → `202 {run_id}` |
| `GET` | `/runs/{id}` | ✓* | Run status + grounded result (tenant-scoped) |
| `GET` | `/runs/{id}/stream` | ✓* | **SSE** live agent trace → terminal |
| `DELETE` | `/me/data` | ✓ | Right-to-be-forgotten (token-scoped tenant purge) |

<sub>*Auth is **fail-closed** outside `local` (Auth0 JWT). Locally it's open for DX; `/health` + `/metrics` stay open for probes/scrape.</sub>

### Example: Plan a city

```json
POST /plan
{ "city": "Kyoto", "interests": ["temples", "food"], "days": 1 }
```

```json
// 202 Accepted
{ "run_id": "0c4f…", "status": "queued" }
```

```json
// GET /runs/{id}  → on success
{
  "status": "succeeded",
  "result": {
    "city": "Kyoto",
    "grounded": true,
    "pois_used": ["Kiyomizu-dera", "Fushimi Inari Taisha", "Gion", "Nishiki Market", "Arashiyama"],
    "days": [{ "day": 1, "items": [{ "name": "Fushimi Inari Taisha", "note": "68 Fukakusa…" }] }],
    "summary_markdown": "Start at dawn at Fushimi Inari…",
    "cost_usd": 0.0021,
    "corrections": 0
  }
}
```

---

## 🧠 How the Agentic RAG Pipeline Works

1. **Dispatch** — `POST /plan`|`/trip` persists a `Run` (tenant-scoped), enqueues a Celery task, and returns a `run_id` in `202` — the API never blocks on the LLM.
2. **Coordinate** — the worker's LangGraph **coordinator** fans out one **worker agent per city** in parallel (`asyncio.gather`), isolating failures so one bad city doesn't sink the trip (**partial results**).
3. **Ground** — each worker geocodes the city, then **retrieves real POIs** from the Qdrant corpus (filtered by the tenant's ACL) with a **live tool fallback** (Overpass / Wikipedia GeoSearch) — never the model's imagination.
4. **Compose** — weather-aware, the worker sequences a day-by-day plan; structured `days` are derived **deterministically from the real POIs** (so map pins can't hallucinate) while the LLM writes the human-readable summary.
5. **Critique** — a **frontier-tier critic agent** checks the draft for invented places + infeasible timing; on a problem it triggers a **capped corrective re-compose** (the critic **fails open** so it never blocks a good plan).
6. **Merge** — per-city plans are stitched together with **inter-city travel legs** (OSRM routing over city centers); the run records status, result, and **real cost**.
7. **Observe** — the whole run is one OpenTelemetry trace (api→worker→agent→llm) with cost, mirrored to Langfuse + Prometheus; logs carry `trace_id`/`run_id`/`tenant_id` only — **never prompt text**.

---

## 🔐 Security

- **Auth0 JWT (RS256), fail-closed** — verified locally against the tenant JWKS; enforced in dev/staging/prod, open only for `local` DX.
- **Per-tenant isolation** — runs are tenant-scoped (cross-tenant IDs return `404`, no probing) and the **RAG ACL is enforced inside Qdrant** (own-private + shared-public), so an app bug can't leak another tenant's data.
- **PII hygiene** — a log processor redacts emails / phone / card-like strings; **no prompt or response text** is ever placed in a span or log (token counts + cost only).
- **Prompt-injection defense** — untrusted city/interest/POI text is sanitized at the trust boundary, with the **critic's grounding gate** as the real enforcement boundary (an invented place is rejected regardless).
- **Abuse + RTBF** — per-tenant fixed-window rate limiting (fail-open for availability) + a token-scoped `DELETE /me/data` right-to-be-forgotten purge.

---

## 🗄️ Database Schema (run store)

```sql
CREATE TABLE runs (
  id          TEXT PRIMARY KEY,            -- run_id (uuid)
  kind        TEXT NOT NULL,               -- 'plan' | 'trip'
  status      TEXT NOT NULL,               -- queued | running | succeeded | failed
  tenant_id   TEXT,                        -- owner; NULL in keyless local mode
  request     JSON NOT NULL,               -- the PlanRequest / TripRequest (JSONB on Postgres)
  result      JSON,                        -- grounded itinerary / trip (set on success)
  cost_usd    REAL DEFAULT 0,              -- real per-run LLM cost
  error       TEXT,                        -- set on failure
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
-- LangGraph checkpoints live in their own tables (Postgres saver) for resume-after-crash.
```

---

## 📊 Results (real numbers, honest scope)

| Metric | Result |
|---|---|
| **Quality (RAG)** | faithfulness **0.857 → 1.0**, grounded-rate **0.71 → 0.86** after adding retrieval grounding |
| **Cost / itinerary** | **~$0.0014–$0.003** (single city) · **$0.0071** (3-city trip) — ~40–200× under the $0.30 ceiling |
| **Tests** | **142** (121 backend pytest + 21 web Vitest) · mypy **strict** clean (57 files) · ruff/bandit clean · `pip-audit` 0 CVEs |
| **Latency NFR** | dispatch p95 **< 150 ms** · full itinerary p50 20s / p95 45s (k6 thresholds, ramps to 50 concurrent) |
| **Deploy** | Docker mesh + live `kind` cluster verified end-to-end · `terraform plan` = **74 resources** against a real AWS account (no apply) |

> **Honest scope:** *demonstrated* at ~50 concurrent locally with a real worker + real LLM calls; the *design target* is ~1M MAU / ~500 peak concurrent with a capacity model arguing the path. Operating at real scale with live traffic and on-call is the next step a production deployment provides — see [`docs/case-study.md`](docs/case-study.md).

---

## 🐳 Deployment

A clean local → cloud path, each stage verified:

1. **Local Docker** — multi-stage non-root images (`api` / `worker` / `web`) + a compose mesh (Postgres + Redis), end-to-end run succeeded.
2. **Local Kubernetes (kind)** — a single Helm chart (`infra/helm/voyantra`), 5/5 pods healthy, real itinerary through the container worker.
3. **Terraform plan** — EKS · RDS (Postgres) · ElastiCache (Redis) · ECR · IRSA · VPC — validated with a real `terraform plan` (74 resources), **no apply**.
4. **GitOps + CI** — GitHub Actions (build → push ECR → **eval gate** → bump values → PR) + ArgoCD (dev auto-sync, **prod manual-gated**); External Secrets ← AWS Secrets Manager.
5. **Cloud promotion** — `dev → staging (load test) → prod`, gated, applied on a real account.

```bash
make check          # lint + strict types + 121 tests
make audit          # pip-audit + pnpm audit + bandit + license gate
bash scripts/kind-up.sh        # one-command local k8s (build → kind load → helm install)
cd infra/terraform && terraform init && terraform plan   # cloud plan (no apply)
```

---

## 🗺️ Roadmap

- 🧭 Self-hosted Overpass (or paid POI API) for interest-filtered grounding at scale
- 🛑 Deeper human-in-the-loop: LangGraph `interrupt` + resume endpoint (approve mid-run)
- 🧊 Safer semantic answer cache (tightly keyed on cities + interests + dates)
- 🔭 Live Alertmanager wiring + real-scale k6 staging load test + scheduled backup drills
- 🧱 Structured per-city multi-day allocation (beyond the day-tripper MVP cap)
- 🌐 Multi-region inference + provisioned throughput for the SLO at true scale

---

## 🤝 About Jillani SofTech

<div align="center">

**[Jillani SofTech](https://www.jillanisoftech.com/)** helps startups, agencies and enterprises build **production-ready AI systems** - RAG platforms, AI agents, LLM SaaS products, workflow automation, full-stack AI applications, production ML systems, MLOps and LLMOps.

We work with clients across the **USA, UK, Germany, EU and the Gulf region**, turning AI ideas into scalable business systems that run reliably on real data.

</div>

### 👨‍💻 Founder - Muhammad Ghulam Jillani
**Full Stack AI Engineer · Lead AI Data Scientist · Founder of Jillani SofTech**

- 🏆 **Top Rated Plus** on Upwork
- 💰 **$100K+ earned** delivering client AI systems
- 🚀 **22 production systems** shipped
- 🎙️ **24x LinkedIn Top Voice in AI**

### 🧩 What We Build
- 🤖 Agentic AI Systems (LangGraph, CrewAI, AutoGen)
- 🔍 RAG & Enterprise Knowledge Pipelines
- 🏗️ AI-powered SaaS Products & Full-Stack AI Apps
- ⚙️ LLM Fine-tuning, Deployment, MLOps & LLMOps
- 🔁 Intelligent Workflow & Document Automation

### 📬 Connect
| | |
|---|---|
| 📞 **Book a 1:1 Call** | https://lnkd.in/emns3fF8 |
| 🌐 **Website** | [jillanisoftech.com](https://www.jillanisoftech.com/) |
| 💼 **Upwork** | [Top Rated Plus Profile](https://www.upwork.com/freelancers/~0146d8e0947a992eee) |
| 🔗 **Portfolio** | [mgjillanimughal.github.io](https://mgjillanimughal.github.io/) |
| 📧 **Email** | [m.g.jillani@jillanisoftech.com](mailto:m.g.jillani@jillanisoftech.com) |

> 💡 **If your AI agent fails with real data, DM me your use case - I'll tell you what's missing.**

---

## 📄 License

Proprietary software developed by **Jillani SofTech**. All rights reserved. Distribution, deployment and customization are governed by the client engagement agreement.

---

<div align="center">

**Built with ❤️ by [Muhammad Ghulam Jillani](https://mgjillanimughal.github.io/) · [Jillani SofTech](https://www.jillanisoftech.com/)**

⭐ If this project helped you, please give it a star - it means the world!

</div>
