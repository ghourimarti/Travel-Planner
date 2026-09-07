# Update Todos — Voyantra (P3 · AI Travel Planner)

Hierarchical task tree: **PHASE → STEP → SUBSTEP**.
Every leaf names the artifact that proves it, so a claim can be checked rather than believed.

```
LEGEND
  [x]  done — artifact exists AND was exercised
  [~]  partial — landed, but a named seam is still open
  [?]  WRITTEN but NEVER EXECUTED   <- the distinction that matters most here
  [ ]  not started
  [-]  blocked / deferred — blocker is named on the line
  [!]  defect found and fixed
  [R]  a claim of mine, corrected
```

> Phases 0–7 were built in **prior sessions**. Their leaves below are reconstructed from the
> artifacts actually present in the tree, not from a session log. Where a leaf could not be
> re-verified in this session it is not marked `[x]` on the strength of the file alone.

---

## PHASE 0 — Repo reconnaissance & baseline report

- [x] **0.1 Inventory the source `demo/`**
  - [x] 0.1.1 Enumerate the Streamlit entrypoint, prompt strings and inline API calls
  - [x] 0.1.2 Record what worked end-to-end (the demo did produce itineraries)
  - [x] 0.1.3 Record what only appeared to work (no tests, no typing, no retries)
- [x] **0.2 Dependency & runtime audit**
  - [x] 0.2.1 Pin the Python version and resolve the true import graph
  - [x] 0.2.2 Separate real runtime deps from notebook-era leftovers
- [x] **0.3 Name the anti-patterns to be removed**
  - [x] 0.3.1 `os.getenv` returning `None` silently -> config must fail fast
  - [x] 0.3.2 File logging disconnected from the pipeline -> stdout JSON logging
  - [x] 0.3.3 Bare `except` swallowing provider errors -> typed exception hierarchy
  - [x] 0.3.4 No cost accounting anywhere -> per-call token + USD capture
- [x] **0.4 Baseline report written and accepted**

## PHASE 1 — Requirements & NFR targets

- [x] **1.1 Functional scope**
  - [x] 1.1.1 Single-city itinerary, N days, grounded in real POIs
  - [x] 1.1.2 Multi-city trip as a first-class case (not N single trips stapled together)
  - [x] 1.1.3 Human-in-the-loop review of a produced plan
- [x] **1.2 Non-functional targets**
  - [x] 1.2.1 Latency budget per plan, and a streaming contract so it is survivable
  - [x] 1.2.2 Cost ceiling per itinerary + a hard kill-switch above it
  - [x] 1.2.3 Degradation policy: partial answer beats no answer
  - [x] 1.2.4 Reproducibility: same input + same seed -> comparable eval scores
- [x] **1.3 Out of scope, explicitly** (booking, payments, live pricing, accounts-at-scale)

## PHASE 2 — Architecture Decision Log

- [x] **2.1 Twenty-two decisions taken, each with options + rationale + scope** — `docs/DECISION_LOG.md`
  - [x] 2.1.1 D1 Primary database · D2 Vector database
  - [x] 2.1.2 D3 Agent architecture — **Option C, multi-agent**
  - [x] 2.1.3 D4 LLM provider & model tiering — **Option B, Groq first then OpenAI**
  - [x] 2.1.4 D5 Embedding model — flagged *most expensive to reverse*
  - [x] 2.1.5 D6 Orchestration framework · D7 Backend language & framework
  - [x] 2.1.6 D8 Frontend & streaming UX
  - [x] 2.1.7 D9 Authentication & authorization — **Option C, Auth0**
  - [x] 2.1.8 D10 Caching strategy
  - [x] 2.1.9 D11 Queue & async work — **Option B, Celery + Redis**
  - [x] 2.1.10 D12 Inference serving · D13 Observability
  - [x] 2.1.11 D14 Cloud provider · D15 Containers, orchestration & IaC
  - [x] 2.1.12 D16 CI/CD · D17 Secrets & configuration
  - [x] 2.1.13 D18 Security posture & threat model
  - [x] 2.1.14 D19 Evaluation strategy · D20 Cost controls
  - [x] 2.1.15 D21 Failure-mode & degradation · D22 Repo structure
- [x] **2.2 At-a-glance summary table** — options / pick / why / pros / cons / maturity tier
- [x] **2.3 Persisted as a document rather than chat scrollback**
- [x] **2.4 Local-inference amendment kept OUT of the original file** *(per instruction)*
  - [x] 2.4.1 New file created — `docs/DECISION_LOG_LOCAL_INFERENCE.md`
  - [x] 2.4.2 D23 local engine choice · D24 chain shape, as dated amendments
  - [x] 2.4.3 `docs/DECISION_LOG.md` confirmed byte-unchanged

## PHASE 3 — Risk-front-loaded transformation plan

- [x] **3.1 Thirteen steps ordered by risk retired per step, not by convenience**
  - [x] 3.1.1 Most-expensive-to-reverse first (embeddings, repo shape, config)
  - [x] 3.1.2 Each step carries Changes / Tests / Verify / Definition-of-Done
  - [x] 3.1.3 Each step ends green — lint, types, tests; never "fix it in the next step"
- [x] **3.2 Rollback position defined for every step**

---

## PHASE 4 — Transformation build (S1–S13)

### S1 · Monorepo + `tp_core` foundation
- [x] **S1.1 uv workspace** — `pyproject.toml`, `uv.lock`, five packages + three apps
- [x] **S1.2 Typed configuration that fails fast** — `tp_core/settings.py`
  - [x] S1.2.1 pydantic-settings; a missing required key raises at import, not at first call
  - [x] S1.2.2 `extra="ignore"` so adding an env var never breaks startup
- [x] **S1.3 Structured logging to stdout** — `tp_core/logging.py` (structlog, JSON)
- [x] **S1.4 Exception hierarchy** — `tp_core/exceptions.py` (`ConfigError` and friends)
- [x] **S1.5 Gate wired and green** — strict mypy + ruff + pytest (6 tests at the time)
- [x] **S1.6 Implements D17 (config) and D22 (repo)** — recorded in commit `24a8f3b`

### S2 · External tools layer
- [x] **S2.1 Shared HTTP client with timeouts + retry** — `tp_tools/_http.py`
- [x] **S2.2 Geocoding** — `tp_tools/geocode.py` · 3 tests
- [x] **S2.3 POI lookup (Overpass / OSM)** — `tp_tools/pois.py` · 6 tests
- [x] **S2.4 Routing** — `tp_tools/routing.py` · 2 tests
- [x] **S2.5 Weather** — `tp_tools/weather.py` · 1 test
- [x] **S2.6 Typed payloads, not dicts** — `tp_tools/models.py`
- [~] **S2.7 Self-hosted Overpass** — `make downv-overpass` kept deliberately separate
  - [-] S2.7.1 OSM import is a 2–4 h job; its volume must never be pruned (see 8.4.8.3)

### S3 · Retrieval / RAG
- [x] **S3.1 Corpus construction** — `tp_retrieval/corpus.py`
- [x] **S3.2 Embedder behind an interface** — `tp_retrieval/embedder.py` (D5, hardest to reverse)
- [x] **S3.3 Vector store adapter (Qdrant)** — `tp_retrieval/vectorstore.py`
- [x] **S3.4 Ingestion pipeline** — `tp_retrieval/ingest.py`, `make ingest`
- [x] **S3.5 Retrieval + reranking** — `retrieve.py`, `rerank.py` · 6 tests
- [~] **S3.6 Operational hazard documented** — index and query embedder must match
  - [~] S3.6.1 A mismatch degrades RAG **silently**; no automated guard exists yet

### S4 · LLM gateway + tiering
- [x] **S4.1 Provider enum + tiers** — `tp_core/llm/types.py` (CHEAP / MID / FRONTIER)
- [x] **S4.2 Model catalogue per tier** — `llm/models.py` (`TIER_ROUTING`) · 3 tests
- [x] **S4.3 Provider adapters** — `llm/providers.py` (Groq, OpenAI, Anthropic)
- [x] **S4.4 Gateway with failover + token/cost capture** — `llm/gateway.py` · 5 tests
- [x] **S4.5 Transient vs permanent failure split** — a 4xx is our bug, not the venue's

### S5 · Agent graph
- [x] **S5.1 Graph state** — `tp_agents/state.py`
- [x] **S5.2 Nodes** — `tp_agents/nodes.py` (retrieve -> ground -> draft)
- [x] **S5.3 Prompts as code, versioned** — `tp_agents/prompts.py`
- [x] **S5.4 Structured output schemas** — `tp_agents/schemas.py` (`Itinerary`, `TripItinerary`)
- [x] **S5.5 Graph assembly** — `tp_agents/graph.py::build_planner_graph` · 10 tests

### S6 · Critic + corrective loop
- [x] **S6.1 Critic pass over the drafted itinerary** — `tp_agents/critic.py` · 2 tests
- [x] **S6.2 Bounded correction cycles** — a loop that cannot run away
- [x] **S6.3 Verified live** — the Kyoto run took **1 critic correction** (see 8.5.4)

### S7 · API surface
- [x] **S7.1 FastAPI app** — `apps/api/src/tp_api/main.py`
- [x] **S7.2 Plan / run / stream endpoints** — 16 tests in `apps/api/tests/test_api.py`
- [x] **S7.3 Container** — `apps/api/Dockerfile`
- [x] **S7.4 Health and readiness mean different things**

### S8 · Multi-city coordinator
- [x] **S8.1 Coordinator fans out per city, then reconciles** — `tp_agents/coordinator.py`
- [x] **S8.2 Per-city worker reuses the single-city graph** — no second implementation
- [x] **S8.3 Trip-level schema** — `TripItinerary` · 2 tests

### S9 · Async execution — dispatch · checkpointer · SSE
- [x] **S9.1 Celery app + Redis broker** — `tp_core/celery.py` (D11)
- [x] **S9.2 Worker app** — `apps/worker/`, `make worker`
- [x] **S9.3 Run registry + persistence** — `tp_core/runs.py` (5 tests), `tp_core/db.py`
- [x] **S9.4 Graph checkpointer** — `tp_agents/checkpoint.py` · 3 tests
- [x] **S9.5 Event bus** — `tp_core/events.py`
- [x] **S9.6 SSE streaming to the browser** — `test_stream.py` · 2 tests
- [x] **S9.7 Committed** — `ae1fda8`, includes S9c

### S10 · Caching + cost controls
- [x] **S10.a Caching + retry** — `tp_core/cache.py` · 4 tests (D10)
- [x] **S10.b Cap + kill-switch + budget gate** — `tp_core/control.py` (2), `test_cost.py` (2),
      `test_budget.py` (1)
  - [-] S10.b.1 **Awaiting commit** — code landed, not yet committed

### S11 · Observability
- [x] **S11.1 OpenTelemetry tracing** — `tp_core/tracing.py` · 4 tests
- [x] **S11.2 Langfuse LLM tracing** — keys live in `.env`
- [x] **S11.3 Prometheus metrics** — `tp_core/metrics.py` · 4 tests
- [x] **S11.4 Prometheus + Grafana + Loki/Promtail** — `infra/observability/`
  - [x] S11.4.1 `prometheus.yml` · `promtail.yml` · `grafana-datasources.yml`
  - [x] S11.4.2 Dashboard — `infra/observability/dashboards/voyantra.json`
- [x] **S11.5 Alerting** — `alerts.yaml` + `alertmanager.yml`
- [x] **S11.6 Compose stack** — `docker-compose.observability.yml`, `make observability`

### S12 · Security + Auth0
- [x] **S12.1 JWT verification** — `tp_core/auth.py` · 5 tests (D9)
- [x] **S12.2 ACL enforced at retrieval, not after** — `tp_core/guard.py` · 4 tests
- [x] **S12.3 PII redaction on the logging path**
- [x] **S12.4 Prompt-injection suite** — `packages/agents/tests/test_injection.py` · 3 tests
- [x] **S12.5 Rate limiting** — `tp_core/ratelimit.py` · 4 tests
- [x] **S12.6 Supply-chain gates** — `make audit-deps` · `sast` · `secrets` · `licenses` · `audit`

### S13 · Next.js frontend (Streamlit retired)
- [x] **S13.1 App Router skeleton** — `apps/web/src/app/layout.tsx`, `middleware.ts`
- [x] **S13.2 Marketing surface** — 9 routes under `app/(marketing)/`
- [x] **S13.3 Product surface** — 8 routes under `app/app/`
  - [x] S13.3.1 `plan/` · `runs/[id]/` · `trips/` · `explore/` · `destinations/[slug]/`
  - [x] S13.3.2 `settings/` · `profile/`
- [x] **S13.4 Route handlers** — `api/plan`, `api/trip`, `api/runs/[id]`, `api/runs/[id]/stream`
- [x] **S13.5 Auth** — Auth0 (`lib/auth0.ts`) + Google OAuth + a dev-login escape hatch
- [x] **S13.6 Trace UI** — `components/app/trace-timeline.tsx` (+ component test)
- [x] **S13.7 Map** — `components/app/map-view.tsx`, `lib/map.ts` (MapLibre)
- [x] **S13.8 Live run streaming hook** — `hooks/use-run-stream.ts` (+ test)
- [x] **S13.9 UI kit** — 10 primitives under `components/ui/`
- [x] **S13.10 Vitest suite** — 7 test files across `lib/`, `hooks/`, `components/`
- [x] **S13.11 Container** — `apps/web/Dockerfile`
- [x] **S13.12 Streamlit demo retired from the shipping tree**

---

## PHASE 5 — Production hardening

- [x] **5.1 Chaos tests** — `packages/agents/tests/test_chaos.py` · 3 tests
- [x] **5.2 Backup + restore drill** — `scripts/backup_restore_drill.sh`
- [x] **5.3 Load test path** — `make load`
- [x] **5.4 Evaluation harness** — `packages/eval/`
  - [x] 5.4.1 Golden set — `tp_eval/golden.py`
  - [x] 5.4.2 Runner + CLI — `runner.py`, `cli.py`, `__main__.py`
  - [x] 5.4.3 Metrics + LLM judge — `metrics.py`, `judge.py`, `ragas_judge.py`
  - [x] 5.4.4 CI gate — `tp_eval/gate.py` · 6 tests
  - [x] 5.4.5 Baseline recorded — `packages/eval/baselines/baseline-rag.json`
- [x] **5.5 Degradation behaviour proven** — a partial itinerary rather than a 500

## PHASE 6 — Deployment

- [x] **6.1 Docker Compose, split by concern**
  - [x] 6.1.1 `docker-compose.data.yml` — Postgres, Redis, Qdrant, Overpass
  - [x] 6.1.2 `docker-compose.app.yml` — api, worker, web
  - [x] 6.1.3 `docker-compose.observability.yml`
  - [x] 6.1.4 `docker-compose.gpu.yml` — added this session (see 8.4.1)
- [x] **6.2 Local Kubernetes (kind)** — `scripts/kind-up.sh` / `kind-down.sh`, `infra/kind/`
  - [~] 6.2.1 **Image drift unreconciled** — `.env` pins `v1.31.2`, the cluster runs `v1.31.6`
- [x] **6.3 Helm chart** — `infra/helm/voyantra/templates/`, 11 templates
  - [x] 6.3.1 Workloads — `api.yaml` · `worker.yaml` · `web.yaml`
  - [x] 6.3.2 Data — `postgres.yaml` · `redis.yaml`
  - [x] 6.3.3 Config + secrets — `configmap.yaml` · `secret.yaml` · `externalsecret.yaml`
  - [x] 6.3.4 Identity — `serviceaccount.yaml` (IRSA)
- [x] **6.4 Terraform / AWS** — `infra/terraform/`, 10 files
  - [x] 6.4.1 Network — `vpc.tf`, plus providers / versions / variables / outputs
  - [x] 6.4.2 Compute — `eks.tf`
  - [x] 6.4.3 Data — `rds.tf` · `elasticache.tf`
  - [x] 6.4.4 Registry — `ecr.tf`
  - [x] 6.4.5 Identity — `irsa.tf`
  - [ ] 6.4.6 **GPU node group + scale-to-zero** — not written
- [x] **6.5 ArgoCD GitOps** — `infra/argocd/`
  - [x] 6.5.1 `project.yaml` + `application-dev/staging/prod.yaml`
  - [-] 6.5.2 **Cloud apply is user-run** — never executed from here
- [x] **6.6 CI/CD** — `.github/workflows/`
  - [x] 6.6.1 `ci.yml` — lint, types, tests
  - [x] 6.6.2 `cd.yml` — build, push, deploy
  - [x] 6.6.3 `promote.yml` — dev -> staging -> prod behind the eval gate

## PHASE 7 — Postmortem & portfolio writeup

- [x] **7.1 Case study written** — `case-study.md`
- [x] **7.2 Portfolio README** — `README2.md`; public `README.md` in tree
- [x] **7.3 Screenshots captured** — `screenshots/`
- [x] **7.4 Internal labels neutralised for publication** — commit `8187988`
- [x] **7.5 Private planning notes untracked** — commits `02b19e5`, `c676002`, `3424619`

---

## PHASE 8 — Local inference venue + repo ergonomics *(this session)*

### 8.1 · Makefile restructure
- [x] **8.1.1 Boxed section titles, then a documentation block, then the commands**
- [x] **8.1.2 Every variable declared once, in a single section at the top**
- [x] **8.1.3 Grew 196 -> 616 lines, 35 -> 58 targets, 13 boxed sections**
- [x] **8.1.4 Engine / GPU-profile resolution block**
  - [x] 8.1.4.1 `ENGINE=vllm|sglang|none` maps to profile + chain + what to stop
  - [x] 8.1.4.2 An unknown value `$(error ...)`s instead of running the wrong thing
- [x] **8.1.5 Independent `vllm-*` family** — `vllm-up` · `-down` · `-upv` · `-downv` · `-test`
- [x] **8.1.6 Independent `sglang-*` family** — the same five, touching only SGLang
- [x] **8.1.7 One-command full bring-up** — `make up-vllm` / `make up-sglang`
  - [x] 8.1.7.1 image (pull if absent) -> container -> weights -> load -> **serve**
  - [R] 8.1.7.2 I claimed `up-with-engine` exporting `SERVING_CHAIN` made `ENGINE=`
        authoritative. **It had no consumer** — `docker-compose.app.yml` uses an explicit
        `environment:` allowlist, not `env_file`, so the var reached no container.
  - [x] 8.1.7.3 **FIXED** — `ENGINE_URL_ENV` added per branch; the target now exports the
        engine URL alongside the chain, and `app.yml` names both under `environment:`
  - [!] 8.1.7.4 **Ordering bug found and fixed** — the app was started BEFORE the engine,
        so its opening requests failed the local leg, tripped the breaker and were
        answered (and billed) by a hosted venue. Engine now comes up first.
- [x] **8.1.8 Support targets** — `which-engine` · `engine-guide` · `webui` · `clean-models`
- [x] **8.1.9 Benchmarks** — `bench-engine` · `bench-groq` · `bench-openai`
- [!] **8.1.10 `.PHONY` kept on a single line** — the Bash tool mangles line continuations
- [x] **8.1.11 Default engine is SGLang**
- [R] **8.1.12 False "orphan targets" alarm was mine** — my checker's regex excluded `=`,
      and help strings contain `SERVING_CHAIN=...`. The instrument was wrong, not the system.

### 8.2 · `.env` / `.env.example` restructure
- [x] **8.2.1 Confirmed a prior session had already restructured both** — 76 vars, 57 sections
  - [R] 8.2.1.1 A stale `Read` showed 239 lines / 74 vars / 26 trailing comments; disk had 490
        lines. One command from overwriting prior work. **Rule adopted: verify with bash.**
- [x] **8.2.2 Added a `LOCAL INFERENCE` section** — engine, URLs, models, chains, breaker
- [x] **8.2.3 Added inference-tier ports** — vLLM 3019 · SGLang 3020 · WebUI 3021
- [x] **8.2.4 Both files now 92 vars, zero drift between them**
- [x] **8.2.5 Zero trailing comments** — `VAR=x  # note` parses the comment into the value
- [x] **8.2.6 Real secrets preserved byte-exactly and never sent anywhere**
- [x] **8.2.7 `SERVING_CHAIN` ships EMPTY** — legacy routing until you opt in

### 8.3 · Serving chain + circuit breaker
- [x] **8.3.1 Chain grammar + parser** — `tp_core/llm/venues.py`
  - [x] 8.3.1.1 `local` · `local-vllm` · `local-sglang` · `groq` · `openai` · `anthropic`
  - [x] 8.3.1.2 `venue:model` overrides the model for that call-point
  - [x] 8.3.1.3 A bare `sglang` is **rejected at startup**, and the error names the fix
  - [x] 8.3.1.4 Duplicate venue, unknown venue and empty chain each raise `ConfigError`
  - [x] 8.3.1.5 A list, not priority numbers — numbers split identity from order
- [x] **8.3.2 Two-level configuration (D24 as amended)**
  - [x] 8.3.2.1 `SERVING_CHAIN` — one baseline order for every tier
  - [x] 8.3.2.2 `CHAIN_CHEAP` / `CHAIN_MID` / `CHAIN_FRONTIER` override per tier
  - [x] 8.3.2.3 `raw_chain_for_tier()` — narrow beats broad; empty means "unset", not "empty"
  - [x] 8.3.2.4 Default leaves FRONTIER hosted — one loaded 7B cannot be three tiers
  - [R] 8.3.2.5 I first built a single chain against an approved per-tier design, because I
        coded before re-reading D24. Resolved as the hybrid above, at your call.
- [x] **8.3.3 Circuit breaker** — `tp_core/llm/circuit.py`
  - [x] 8.3.3.1 CLOSED / OPEN / HALF_OPEN; threshold 3, cooldown 30 s
  - [x] 8.3.3.2 HALF_OPEN admits **exactly one** probe
  - [x] 8.3.3.3 A 4xx does not count against a venue
  - [x] 8.3.3.4 `snapshot()` reports every known leg, not only the one that moved
  - [!] 8.3.3.5 **Clock bug found and fixed** — `snapshot()` mixed an injected clock with
        `time.monotonic()`, so a just-opened leg read half-open. Caught by a new test.
  - [x] 8.3.3.6 Scope recorded as per-process, with the Redis trade-off written down
- [x] **8.3.4 Local provider** — `LocalEngineProvider` in `llm/providers.py`
  - [x] 8.3.4.1 `AsyncOpenAI(base_url=...)` — one adapter serves both engines
  - [x] 8.3.4.2 `max_retries=0` — the chain retries, not the client
  - [x] 8.3.4.3 `cost_usd=0.0` set explicitly (0.0 is a measurement, not a blank)
- [x] **8.3.5 Gateway rework** — `llm/gateway.py`
  - [x] 8.3.5.1 `chains: dict[Tier, list[ChainLeg]]` + `_resolve_chain(tier)`
  - [x] 8.3.5.2 Precedence: per-tier -> baseline -> legacy `TIER_ROUTING`
  - [x] 8.3.5.3 Breaker consulted before each leg; a leg with no key is skipped
        **with a warning naming it** — never a silent downgrade
  - [x] 8.3.5.4 **Backward compatible by construction** — an empty chain reproduces
        legacy routing exactly
- [x] **8.3.6 Settings** — `serving_chain` · `serving_engine` · per-tier chains · URLs ·
      models · `circuit_failure_threshold` · `circuit_cooldown_seconds`
- [x] **8.3.7 Tests** — `packages/core/tests/test_llm_local_venues.py`, 21 test functions
  - [x] 8.3.7.1 Includes a test pinning that a 7B never reaches FRONTIER

### 8.4 · GPU venue infrastructure
- [!] **8.4.0 The extension was never wired to any container** — found by verification,
      not by a test. `docker-compose.app.yml` passes an explicit `environment:` allowlist;
      none of `SERVING_*`, `CHAIN_*`, `VLLM_URL`, `SGLANG_URL`, `CIRCUIT_*` was in it.
  - [x] 8.4.0.1 Proven inside both containers — every one of them read empty
  - [R] 8.4.0.2 This is why the app kept working: an empty chain falls back to legacy
        `TIER_ROUTING`, so the invalid `SERVING_CHAIN=sglang,...` in `.env` never reached
        a container and never raised. **Luck, not design.**
  - [x] 8.4.0.3 **FIXED** — 14 vars added to `environment:` on api **and** worker;
        `compose config` validates; ruff clean and 150 passed afterwards
- [x] **8.4.1 `docker-compose.gpu.yml`**
  - [x] 8.4.1.1 vLLM :3019 (`gpu-vllm`) · SGLang :3020 (`gpu-sglang`) · WebUI :3021 (`webui`)
  - [x] 8.4.1.2 Shared `tp_hf_cache` volume — one 5.5 GB download serves either engine
  - [x] 8.4.1.3 `shm_size: 8gb`, `ipc: host`
  - [x] 8.4.1.4 Healthcheck polls the engine's own `/health`, `start_period: 900s`
        — `--wait` alone returns while 5.5 GB of weights are still loading
- [x] **8.4.2 Preflight** — `scripts/engine_preflight.sh` · **run, works**
  - [x] 8.4.2.1 Sizes need as `weights x1.4 + 1.5 GB`; refuses in ~2 s rather than exit 137
        after twenty minutes
  - [x] 8.4.2.2 Names the container holding the card and prints the command to stop it
- [x] **8.4.3 Failure diagnostic** — `scripts/engine_failed.sh`
  - [x] 8.4.3.1 Branches on **real** container state: running / 137 / crash / gone
  - [x] 8.4.3.2 Refuses to guess — the obvious "it is still loading" version misleads
        exactly when it matters
- [x] **8.4.4 Benchmark harness** — `scripts/bench_venue.py` · **RUN, 5/5 succeeded**
  - [x] 8.4.4.1 TTFT p50 **50 ms** / p95 559 ms · TPOT p50 **15.2 ms** · **60.8 tok/s**
  - [x] 8.4.4.2 Warmup discard justified by the data: warmup TTFT 246 ms, run-1 559 ms,
        then ~50 ms steady — the cold request is a different machine
  - [!] 8.4.4.3 `make bench-groq` **fails 404** — see 8.8
- [x] **8.4.5 Hardware recon** — RTX 3060 12 GB, cc 8.6; passthrough verified inside a container
- [x] **8.4.6 Model chosen** — `Qwen/Qwen2.5-7B-Instruct-AWQ`, INT4, ~5.5 GB, ungated
- [x] **8.4.7 Both engine images confirmed already pulled** — vLLM 30.8 GB, SGLang 47 GB
- [x] **8.4.8 Disk reclaim, reviewed line by line before deleting**
  - [x] 8.4.8.1 Docker internals + odds (1.13 GB) · stale p61 tags (1.80 GB) · dupes (8.14 GB)
  - [!] 8.4.8.2 Prevented deletion of the 30.8 GB vLLM image that read as "unused"
  - [!] 8.4.8.3 Prevented `docker volume prune` — **547 of 565** volumes read as dangling,
        including the 2–4 h OSM import, because `compose down` removes containers
  - [R] 8.4.8.4 I first claimed ~11 GB reclaimed; actual was **6.8 GB** — `docker images`
        counts shared base layers once per image
  - [ ] 8.4.8.5 VHDX compact, to hand the space back to Windows — not done

### 8.5 · Venue on the response contract + metrics
- [x] **8.5.1 Metrics** — `tp_core/metrics.py`
  - [x] 8.5.1.1 `LLM_TOKENS` · `LLM_COST` counters
  - [x] 8.5.1.2 `CIRCUIT_STATE` gauge, `multiprocess_mode="mostrecent"`
  - [x] 8.5.1.3 Labels bounded to enum values — no unbounded cardinality
  - [x] 8.5.1.4 `record_venue_usage()` + `record_circuit()`
- [x] **8.5.2 `venues` added to the schemas** — `Itinerary` and `TripItinerary`
- [x] **8.5.3 Accumulated along the whole path**
  - [x] 8.5.3.1 `nodes.py` — union of this response's venue with the prior set
  - [x] 8.5.3.2 `critic.py` — the critic's own venue merged in
  - [x] 8.5.3.3 `coordinator.py` — union across every city
  - [x] 8.5.3.4 Rides the existing `result` JSON column — **no DB migration**
- [x] **8.5.4 Proven end-to-end on a real run**
  - [x] 8.5.4.1 Kyoto, 1 day, 5 POIs, $0.00656, 1 critic correction
  - [x] 8.5.4.2 `venues: ['openai']` survives `model_dump(mode="json")`

### 8.6 · Documentation
- [x] **8.6.1 `docs/DECISION_LOG_LOCAL_INFERENCE.md`** — 299 -> 441 lines, dated amendments
  - [x] 8.6.1.1 D24 recorded as the **hybrid actually built**, not as first drafted
  - [x] 8.6.1.2 An explicit verified-vs-unverified table
- [x] **8.6.2 `docs/gpu-venue.md`** — the bring-up runbook
  - [x] 8.6.2.1 "A liveness check is not a capacity check"
  - [x] 8.6.2.2 "Declared is not working"
  - [x] 8.6.2.3 vLLM `--gpu-memory-utilization` (fraction of **free**) vs SGLang
        `--mem-fraction-static` (fraction of **total**) — not the same knob
  - [x] 8.6.2.4 One engine at a time: 0.80 + 0.70 is 150% of the card, and it **wedges**
        at "Starting to load model" rather than failing fast
  - [x] 8.6.2.5 Never `docker volume prune`
  - [x] 8.6.2.6 The first download must not be interrupted — `huggingface_hub` does not resume
  - [x] 8.6.2.7 `make webui` is deliberately the unguarded path, so engine quality and
        product quality are judged separately
- [x] **8.6.3 `docs/DECISION_LOG.md` left untouched** — verified

### 8.7 · Bring-up and measurement
- [x] **8.7.1 Engine STARTED and PROVEN GENERATING** — healthy in 360 s; `/v1/chat/completions`
      returned real text; `max_total_num_tokens=11881`, 10406 MiB used / 1708 MiB free.
      Original blocker note follows:
- [x] **8.7.1-orig Start an engine and prove it generates** — **UNBLOCKED**:
      `p5-medical-chatbot-sglang-1` exited 30 h ago; the card is free. Engine started and
      is loading; not yet proven to generate.
  - [x] 8.7.1.1 Preflight **correctly refused** — 8980 MiB free vs a 9200 MiB heuristic.
        The check did its job; it was not bypassed blindly.
  - [x] 8.7.1.2 `SGLANG_MEM_FRACTION` 0.70 -> **0.55** to leave ~1.4 GB desktop headroom,
        because the 3055 MiB in use is ordinary Windows desktop, not a stale container
  - [!] 8.7.1.3 SGLang additionally reserves **1024 MiB for CUDA IPC**, which the
        preflight heuristic does not model — first number to lower if it OOMs
- [-] **8.7.2 `make bench-engine` against a live local venue** — blocked by 8.7.1
- [-] **8.7.3 Flip `SERVING_CHAIN=local-sglang,groq,openai` and confirm `venues` reads
      `['local-sglang']`** — blocked by 8.7.1
- [x] **8.7.4 `scripts/ensure_weights.sh`** — WRITTEN and RUNNING, prompted by a real failure
  - [!] 8.7.4.1 First cold start **stalled**: 0.87 GB of 5.5 GB, then **zero bytes for 6
        minutes** while the container sat `unhealthy` and kept holding the GPU.
        Unauthenticated HF downloads are rate-limited and hang without erroring.
  - [x] 8.7.4.2 Weights now fetched in a throwaway container with **no `--gpus`** — a
        stalled download must not park the card
  - [x] 8.7.4.3 Stall detection by sampling cache growth; a zero-growth window is treated
        as death and retried. Safe because `.incomplete` blobs resume.
  - [x] 8.7.4.4 Completion verified by **content** (`*.safetensors` present), not exit status
  - [!] 8.7.4.5 **`start_period: 900s` is too short** — it covers a cold *load*, not a cold
        *download* on a rate-limited link. `make sglang-up`'s `--wait-timeout 900` would
        have declared failure on a download that was still alive. Not yet fixed.

---

## GATE — current state

- [x] **G.1 `ruff`** — All checks passed
  - [!] G.1.1 Fixed: `E741` ambiguous name `l` (twice) -> `leg`; line-too-long wrapped
- [x] **G.2 `mypy --strict`** — clean
  - [!] G.2.1 Fixed: `override` typed `str` but assigned `str | None`
- [x] **G.3 `pytest`** — **150 passed**; baseline 128 -> +22, zero regressions
- [x] **G.4 139 test functions across 33 files** (parametrisation expands to 150 cases)
- [x] **G.5 Frontend vitest suite green** — 7 files

## GIT — prepared, never run

- [x] **N.1 Standing constraint honoured** — no `git add` / `commit` / `push` / GitHub op
- [ ] **N.2 Extend the prepared `git add` list to this round**
  - [ ] N.2.1 `Makefile` · `.env.example` · `docker-compose.gpu.yml`
  - [ ] N.2.2 `packages/core/src/tp_core/llm/{venues,circuit,providers,gateway}.py`
  - [ ] N.2.3 `packages/core/src/tp_core/{settings,metrics}.py`
  - [ ] N.2.4 `packages/agents/src/tp_agents/{schemas,nodes,critic,coordinator}.py`
  - [ ] N.2.5 `packages/core/tests/test_llm_local_venues.py`
  - [ ] N.2.6 `scripts/{engine_preflight.sh,engine_failed.sh,bench_venue.py}`
  - [ ] N.2.7 `docs/{DECISION_LOG_LOCAL_INFERENCE.md,gpu-venue.md}` · `update_todos.md`
  - [ ] N.2.8 Still uncommitted from earlier — **S10.b**

## NEXT — the moment the GPU is free

- [-] **X.1** `make sglang-up`
- [-] **X.2** `make which-engine` — confirm the app sees the venue it claims
- [-] **X.3** `curl /v1/chat/completions` — prove it **generates**, not merely that it is `Up`
- [-] **X.4** `make bench-engine` then `make bench-groq` — TTFT / TPOT side by side
- [-] **X.5** Set `SERVING_CHAIN=local-sglang,groq,openai`, re-run a plan, confirm `venues`
      reads `['local-sglang']` and that cost drops toward `$0`
- [-] **X.6** Record the measured numbers in `docs/gpu-venue.md` §7, replacing the `[?]` marks


---

## 8.8 · PROVEN END-TO-END *(2026-09-07)*

- [x] **8.8.1 The whole chain works** — same Kyoto plan, before vs after
  - [x] 8.8.1.1 `venues: ['openai']` -> **`venues: ['local-sglang']`**
  - [x] 8.8.1.2 cost `$0.002487` -> **`$0.00`**
  - [x] 8.8.1.3 17 s vs 15 s — local costs ~2 s of wall clock, not minutes
  - [x] 8.8.1.4 Worker resolves the engine by service DNS (`http://sglang:30000/v1`),
        confirming the shared-compose-project assumption
- [x] **8.8.2 Weights staged** — 6202 MB cached, both shards symlinked, zero `.incomplete`
  - [!] 8.8.2.1 **Xet was the real blocker** — 0 MB/120 s with it, 21 MB/90 s without.
        A token changed nothing (0.19 -> 0.23 MB/s); with Xet off it ran at **3.6 MB/s**.
  - [R] 8.8.2.2 I recommended the HF token as the fix. It was not the cause. I quoted
        ETAs of 7 h then 2 h; the real download took ~20 min once Xet was disabled.
  - [!] 8.8.2.3 `.env` had **two** `HF_TOKEN=` lines; the empty later one silently won.
        Caught only because the script announces AUTHENTICATED/ANONYMOUS out loud.
- [!] **8.8.3 THE GROQ LEG IS DEAD** — found by running the benchmark, not by a test
  - [x] 8.8.3.1 `llama-3.1-8b-instant` and `llama-3.3-70b-versatile` both return **404**;
        Groq now serves `openai/gpt-oss-*` and `qwen/qwen3.*`
  - [x] 8.8.3.2 Both are in `TIER_ROUTING` for CHEAP, MID and FRONTIER
  - [R] 8.8.3.3 This explains the pre-change run reading `venues: ['openai']` when D4
        specifies **Groq first**: the free leg was 404ing and traffic fell silently to
        the paid one. The app has been paying OpenAI for work Groq was meant to do.
  - [ ] 8.8.3.4 **NOT FIXED** — choosing a replacement model is a D4 decision (quality
        and cost), not a typo fix. Needs a call before editing `TIER_ROUTING`.
- [x] **8.8.4 Preflight passed on its own merits** — 9270 MiB free vs 9200 needed;
      no `SKIP_MEM_CHECK` override was used in the end
- [R] **8.8.5 My throughput estimate was too pessimistic** — I predicted 25-40 tok/s and
      a 40-60 s itinerary. Actual: **60.8 tok/s** and **17 s**. The latency worry that
      prompted relaxing the p95 target was unfounded; no threshold needs moving.
