# Case Study — AI Travel Planner (Agentic RAG, production rebuild)

> A bootcamp Streamlit demo (one LLM call, no tests, no API) transformed into a **production-grade, multi-agent, multi-city travel planner** that grounds every itinerary in real places — full async backend, eval gate, observability, security, IaC, and a commercial Next.js front end. Built solo as a uv monorepo, decision-driven, one reviewable commit per step.
>
> **Stack:** Python · FastAPI · LangGraph (multi-agent) · OpenAI (tiered + cross-provider fallback) · Qdrant · Celery + Redis · Postgres · OpenTelemetry + Langfuse + Prometheus · Auth0 · Next.js 15 / React 19 / MapLibre · Docker · Kubernetes (kind→EKS) · Terraform · Helm · ArgoCD · GitHub Actions.

---

## 1. The problem

The starting point was a portfolio demo: a Streamlit page that took a city + interests and made a single LLM call to write an itinerary. It looked fine and was entirely untrustworthy — it **hallucinated places**, had no tests, no API, no resilience, no cost control, and logged to a file that no pipeline ever read. The goal was to turn it into something a real client could deploy: a planner that recommends **places that actually exist**, scales as a service, and is observable, secure, and cost-bounded.

## 2. What I built

A traveler enters one to five cities, interests, and trip length. A **multi-agent system** plans each city in parallel (a coordinator fans out one worker agent per city), grounds the recommendations in a real POI corpus + live geo/weather/routing data, sequences a day-by-day plan, computes inter-city travel legs, and a **critic agent** checks the draft for invented places and infeasible timing — re-planning if needed. The result streams to the browser live (you watch each step run) and renders on a map. If one city fails, the others still ship (**partial results**); if the data source can't ground a place, the app says so instead of inventing one.

## 3. Architecture

```
Browser (Next.js 15 / React 19, MapLibre map, live trace UI)
   │  same-origin BFF route handlers — Auth0 token attached server-side (never in the browser)
   ▼
FastAPI  ── POST /plan,/trip → persist Run + enqueue → 202 {run_id}     [async dispatch, p95<150ms]
   │         GET /runs/{id}  · GET /runs/{id}/stream (SSE)   · /health · /metrics
   │         Auth0 JWT (fail-closed) · per-tenant rate-limit · kill-switch
   ├─ Postgres (run state + audit, tenant-scoped)        ┌───────────────────────────────┐
   └─ Celery → Redis broker ──────────────────────────►  │  Worker (LangGraph multi-agent)│
                                                          │  coordinator                   │
   Redis caches (geo/POI/weather/route, per-tool TTL)     │   └ per-city worker  (parallel)│
   Qdrant (POI vectors, ~1024-d, tenant ACL)              │       geocode → gather → compose│
                                                          │       (corpus + live tools)    │
   LLM gateway  ── tier: gpt-4o-mini → gpt-4o             │   → critic → corrective loop   │
     fallback: OpenAI → Anthropic → Groq (key-gated)      │   → merge + inter-city legs    │
                                                          └───────────────────────────────┘
Observability: OpenTelemetry trace (api→worker→agent→llm) · Langfuse generations · Prometheus RED+cost
Resume-after-crash: LangGraph Postgres checkpointer · Cost cap + kill switch · PII-redacted JSON logs
```

**Request lifecycle:** the API never blocks on the LLM — it persists a run and returns a `run_id` immediately; the worker executes the graph; the browser polls/streams to terminal. A crashed worker **resumes from the last completed node** (Postgres checkpointer), so a redelivered task doesn't re-spend on work already done.

## 4. Key decisions & trade-offs (from the 22-decision log)

| Decision | Choice | Trade-off accepted |
|---|---|---|
| Agent architecture | **Multi-agent** (coordinator + per-city workers + critic) | More cost/complexity than a single agent — contained with ≤5 workers, hard caps, partial results, and a raised eval bar |
| LLM serving | **Gateway**: tier `gpt-4o-mini`→`gpt-4o`, cross-provider fallback (OpenAI→Anthropic→Groq) | A routing layer to test, in exchange for cost control + provider-outage resilience (the 99.5% SLO can't survive a single provider) |
| Embeddings | OpenAI `text-embedding-3-large` @ **1024-d** (Voyage `voyage-3` optional, same dim) | Pinned the one hard-to-reverse parameter so a future engine swap is a **re-index, not a re-embed** |
| Grounding | Curated POI corpus (Qdrant) **primary** + live tools fallback | Retrieval quality + honesty over "just ask the model" |
| Async | FastAPI dispatch + Celery worker + Postgres checkpointer | Operational complexity, in exchange for resumability + concurrency under long (20–45s) runs |
| Cost | Per-run **+ per-sub-agent** hard caps + kill switch + budget eval gate | Caps can clip quality if mis-tuned — set to the $0.30 NFR ceiling, not a tight relative delta |
| Auth/data | Auth0 JWT (fail-closed) + **ACL enforced in Qdrant** + PII log redaction | Enforcement at the data store can't be bypassed by an app bug |

Full reasoning: [`architecture-decision-log.md`](architecture-decision-log.md) · matrix: [`decision-summary.md`](decision-summary.md).

## 5. Results — real numbers (and honest scope)

**Quality (eval harness, 7-case golden set, LLM-judge):**
- Faithfulness **0.857 → 1.0** and grounded-rate **0.71 → 0.86** after adding RAG grounding (S6) — the measured fix for a confirmed hallucination (the demo invented "Gion"; grounded retrieval replaced it with real Kyoto temples).
- success 1.0 · under-budget 1.0 · honest-on-degrade 1.0 (refuses to invent when it can't ground).

**Cost (real, from per-call accounting):**
- Single-city itinerary: **~$0.0014–$0.003**. Three-city trip (Paris→Barcelona→Rome, grounded, 2 inter-city legs): **$0.0071**.
- That's **~40–200× under** the $0.30/itinerary ceiling — the hard caps are guardrails, not the operating point.

**Performance (NFR targets + load harness):**
- Lightweight dispatch endpoint target **p95 < 150 ms**; full async itinerary target **p50 20s / p95 45s**; **≥99%** of runs reach a terminal state — all encoded as k6 thresholds (`tests/load/plan_smoke.js`, ramps to 50 concurrent).
- **Demonstrated** locally (Docker compose mesh + a live `kind` cluster, real worker, real LLM calls, end-to-end succeeded). **Design target** is ~1M MAU / ~500 peak concurrent; the k6 harness proves ~50 concurrent and a capacity model argues the path to 500.

**Engineering quality:** **142 tests** (121 backend pytest + 21 web Vitest) green · **mypy strict** clean (57 files) · ruff clean · `bandit` 0 findings · `pip-audit` 0 CVEs · chaos tests (LLM / vector-DB / geocode outages all degrade gracefully).

**Deployment:** multi-stage non-root Docker images; single Helm chart verified on a live `kind` cluster (5/5 pods, end-to-end run); Terraform for EKS/RDS/ElastiCache/ECR/IRSA/VPC validated with a real **`terraform plan` = 74 resources** against a live AWS account (no apply); ArgoCD GitOps (dev auto-sync, prod manual-gated) + a CI pipeline with a **real-LLM eval gate** that blocks promotion on quality regression.

## 6. Engineering practices that make it production-grade

- **Eval before features.** The eval harness was built at step 5 of 13 — every later change was measured against a baseline, and the eval is wired as a **CI gate** that fails the build on a quality or budget regression.
- **Observability as a first-class concern.** One run = one distributed OpenTelemetry trace (api→worker→agent→llm) with cost; the same signals feed Prometheus (alertable) and Langfuse (per-step generations) — and **no prompt/response text ever leaves in a span or log** (tokens + cost only; PII redacted).
- **Defense in depth.** Fail-closed JWT auth → tenant-scoped runs + Qdrant ACL → PII redaction → prompt-injection sanitizer with the critic's grounding gate as the real enforcement boundary → per-tenant rate limits.
- **Resilience by design.** Circuit-breaker/retry on every external call; best-effort caching/telemetry that **never fails a run**; cross-provider LLM fallback; partial results on multi-city failure; honest "no answer" over hallucination.
- **One reviewable commit per step**, each with tests, each leaving the repo green and deployable.

## 7. What I'd do differently (and honest limitations)

- **Validate the free data source earlier.** The keyless POI source (Overpass) turned out to WAF-block datacenter IPs; I built a Wikipedia-GeoSearch fallback, but I'd have budgeted for a self-hosted Overpass or a paid POI API from day one rather than discovering it during a live run.
- **Gate multi-agent behind complexity.** For a single-city day trip, one capable agent would do; the coordinator/critic topology earns its cost on multi-city trips. A production v2 would route simple requests to the cheaper single-agent path.
- **Safer answer caching.** I deliberately deferred a semantic full-response cache (a near-miss can return the wrong city's plan); a v2 would key it tightly on `{cities, interests, dates, constraints}` with an eval check on cache hits.
- **The honest ceiling:** this is **built, demonstrated, and load-test-harnessed — not operated at real scale with real traffic.** The k6 run proves ~50 concurrent; 1M MAU and an on-call rotation are experience-gated and require a live production deployment (the Phase-6 `terraform apply` + staging load test, run on a real account). I can architect and demonstrate the patterns; operating them at scale is the next step a real production role provides.

## 8. The consolidated "senior-vs-junior" table

One row per build slice — the single thing in each that signals experience. This is the interview-grade summary of *how* it was built, not just *what*.

| Slice | The tell that signals an experienced engineer |
|---|---|
| **S1 Foundation** | Hermetic tests + **fail-fast typed config** + JSON-to-stdout logging from commit #1 (the two demo anti-patterns fixed at the bottom, not retrofitted). |
| **S2 LLM gateway** | An **anti-corruption layer** over providers + error classification (retryable→fallback, non-retryable→raise); fallback rungs inert without keys. |
| **S3 Tools** | Typed Pydantic tool contracts over keyless OSS data with a resilient shared HTTP client + circuit breaker. |
| **S4 Thin slice** | Shipped the **thinnest end-to-end slice first** to prove integration risk; caught a grounding leak and **reported it honestly** (degraded=True) instead of hiding it. |
| **S5 Eval** | Built the **measurement harness before widening**; fixed (reproducible) fixtures; the eval itself forced a real honesty-bug fix. |
| **S6 RAG** | **Pinned the embedding dimension** with a same-dim fallback so a vector-engine swap is a re-index, not a re-embed; decoupled agents from retrieval via a Protocol. |
| **S7 Critic** | Critic **fails open** (never blocks on an unparseable verdict) and the corrective loop is **capped** (no infinite re-plan). |
| **S8 Multi-city** | Parallel fan-out with **partial results** (one city fails, the rest ship) — added without breaking the single-city contract. |
| **S9 Async** | **Dispatch/state separation** + a checkpointer that provably **resumes after a crash** (deterministic test, no real crash needed). |
| **S10 Cost** | Best-effort cache that **never poisons on a falsy result**; cost cap pre-empts the only re-spend point; kill switch **fails open**. |
| **S11 Observability** | Spans always created but only **exported when configured** (a broken collector never touches the request path); **no prompt text** in spans; bounded-enum metric labels (cardinality discipline). |
| **S12 Security** | **Fail-closed** auth; ACL enforced **at the data store** (un-bypassable); cross-tenant ID → 404 (no probing); injection sanitizer + grounding gate as defense-in-depth. |
| **S13 Frontend** | **BFF** so the token never reaches the browser; keyless-buildable; map library dynamic-imported (never SSR); **deterministic day plan from real POIs** so map pins can't hallucinate. |
| **P5 Hardening** | Split **Done vs Harness-ready** honestly — deferred the 3 items that need live infra rather than faking them; shipped the repo's first CI gate. |
| **P6 Deploy** | Found real bugs **by actually running it** (missing extras, kind cgroup-v1, stale images, a host worker stealing tasks); kept the kind render **byte-unchanged** while the cloud overlay adds IRSA/ExternalSecrets; `terraform plan` against a real account, **no apply**. |

---

## Repo map

```
packages/core/       tp_core: config · logging · exceptions · LLM gateway · cache · cost cap · auth · metrics · tracing · guard · ratelimit
packages/tools/      tp_tools: geocode / POI / weather / routing (keyless OSS + resilient HTTP)
packages/agents/     tp_agents: LangGraph multi-agent graph · coordinator · critic · checkpointer
packages/retrieval/  tp_retrieval: embeddings · Qdrant store (tenant ACL) · hybrid retrieve · rerank · ingest
packages/eval/       tp_eval: golden set · metrics · LLM-judge · CI eval gate
apps/api/            FastAPI: async dispatch · SSE · auth · metrics
apps/worker/         Celery worker running the graph
apps/web/            Next.js 15 (Voyantra): marketing + product, BFF, live trace UI, MapLibre map, Auth0
infra/               Dockerfiles · Helm chart · kind · Terraform (EKS/RDS/ElastiCache/ECR/IRSA) · ArgoCD · alerts
docs/                architecture-decision-log · decision-summary · runbook · production-hardening · this case study
```

## How to run

```bash
uv sync && cp .env.example .env       # set OPENAI_API_KEY
make check                            # lint + type-check + 121 tests
make ingest && make eval-rag          # build the POI index + score quality
make services && make worker && make api   # Postgres+Redis, worker, API
# browser product:  cd apps/web && pnpm install && pnpm dev
```
