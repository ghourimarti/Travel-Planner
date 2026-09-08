# Update Todos — Voyantra (P3 · AI Travel Planner)

Hierarchical task tree: **PHASE → STEP → SUBSTEP**.
Every leaf names the artifact that proves it, so a claim can be checked rather than believed.

| | meaning |
|---|---|
| ✅ | **done** — the artifact exists AND was actually exercised |
| 🔄 | **in progress / partial** — landed, but a named seam is still open |
| ⏳ | **pending** — not started, or written but never run |
| ⏸️ | **blocked / deferred** — the blocker is named on the line |
| ⚠️ | defect found **and fixed** |
| 📝 | a claim of mine, **corrected** |

⏳ is the one to read carefully: code that is written, linted and unit-tested but has
never been executed against the real thing is *not* done, and collapsing it into ✅ is
how "declared" gets mistaken for "working".

> Phases 0–7 were built in **prior sessions**. Their leaves below are reconstructed from the
> artifacts actually present in the tree, not from a session log. Where a leaf could not be
> re-verified in this session it is not marked `[x]` on the strength of the file alone.

---

## PHASE 0 — Repo reconnaissance & baseline report

- ✅ **0.1 Inventory the source `demo/`**
  - ✅ 0.1.1 Enumerate the Streamlit entrypoint, prompt strings and inline API calls
  - ✅ 0.1.2 Record what worked end-to-end (the demo did produce itineraries)
  - ✅ 0.1.3 Record what only appeared to work (no tests, no typing, no retries)
- ✅ **0.2 Dependency & runtime audit**
  - ✅ 0.2.1 Pin the Python version and resolve the true import graph
  - ✅ 0.2.2 Separate real runtime deps from notebook-era leftovers
- ✅ **0.3 Name the anti-patterns to be removed**
  - ✅ 0.3.1 `os.getenv` returning `None` silently -> config must fail fast
  - ✅ 0.3.2 File logging disconnected from the pipeline -> stdout JSON logging
  - ✅ 0.3.3 Bare `except` swallowing provider errors -> typed exception hierarchy
  - ✅ 0.3.4 No cost accounting anywhere -> per-call token + USD capture
- ✅ **0.4 Baseline report written and accepted**

## PHASE 1 — Requirements & NFR targets

- ✅ **1.1 Functional scope**
  - ✅ 1.1.1 Single-city itinerary, N days, grounded in real POIs
  - ✅ 1.1.2 Multi-city trip as a first-class case (not N single trips stapled together)
  - ✅ 1.1.3 Human-in-the-loop review of a produced plan
- ✅ **1.2 Non-functional targets**
  - ✅ 1.2.1 Latency budget per plan, and a streaming contract so it is survivable
  - ✅ 1.2.2 Cost ceiling per itinerary + a hard kill-switch above it
  - ✅ 1.2.3 Degradation policy: partial answer beats no answer
  - ✅ 1.2.4 Reproducibility: same input + same seed -> comparable eval scores
- ✅ **1.3 Out of scope, explicitly** (booking, payments, live pricing, accounts-at-scale)

## PHASE 2 — Architecture Decision Log

- ✅ **2.1 Twenty-two decisions taken, each with options + rationale + scope** — `docs/DECISION_LOG.md`
  - ✅ 2.1.1 D1 Primary database · D2 Vector database
  - ✅ 2.1.2 D3 Agent architecture — **Option C, multi-agent**
  - ✅ 2.1.3 D4 LLM provider & model tiering — **Option B, Groq first then OpenAI**
  - ✅ 2.1.4 D5 Embedding model — flagged *most expensive to reverse*
  - ✅ 2.1.5 D6 Orchestration framework · D7 Backend language & framework
  - ✅ 2.1.6 D8 Frontend & streaming UX
  - ✅ 2.1.7 D9 Authentication & authorization — **Option C, Auth0**
  - ✅ 2.1.8 D10 Caching strategy
  - ✅ 2.1.9 D11 Queue & async work — **Option B, Celery + Redis**
  - ✅ 2.1.10 D12 Inference serving · D13 Observability
  - ✅ 2.1.11 D14 Cloud provider · D15 Containers, orchestration & IaC
  - ✅ 2.1.12 D16 CI/CD · D17 Secrets & configuration
  - ✅ 2.1.13 D18 Security posture & threat model
  - ✅ 2.1.14 D19 Evaluation strategy · D20 Cost controls
  - ✅ 2.1.15 D21 Failure-mode & degradation · D22 Repo structure
- ✅ **2.2 At-a-glance summary table** — options / pick / why / pros / cons / maturity tier
- ✅ **2.3 Persisted as a document rather than chat scrollback**
- ✅ **2.4 Local-inference amendment kept OUT of the original file** *(per instruction)*
  - ✅ 2.4.1 New file created — `docs/DECISION_LOG_LOCAL_INFERENCE.md`
  - ✅ 2.4.2 D23 local engine choice · D24 chain shape, as dated amendments
  - ✅ 2.4.3 `docs/DECISION_LOG.md` confirmed byte-unchanged

## PHASE 3 — Risk-front-loaded transformation plan

- ✅ **3.1 Thirteen steps ordered by risk retired per step, not by convenience**
  - ✅ 3.1.1 Most-expensive-to-reverse first (embeddings, repo shape, config)
  - ✅ 3.1.2 Each step carries Changes / Tests / Verify / Definition-of-Done
  - ✅ 3.1.3 Each step ends green — lint, types, tests; never "fix it in the next step"
- ✅ **3.2 Rollback position defined for every step**

---

## PHASE 4 — Transformation build (S1–S13)

### S1 · Monorepo + `tp_core` foundation
- ✅ **S1.1 uv workspace** — `pyproject.toml`, `uv.lock`, five packages + three apps
- ✅ **S1.2 Typed configuration that fails fast** — `tp_core/settings.py`
  - ✅ S1.2.1 pydantic-settings; a missing required key raises at import, not at first call
  - ✅ S1.2.2 `extra="ignore"` so adding an env var never breaks startup
- ✅ **S1.3 Structured logging to stdout** — `tp_core/logging.py` (structlog, JSON)
- ✅ **S1.4 Exception hierarchy** — `tp_core/exceptions.py` (`ConfigError` and friends)
- ✅ **S1.5 Gate wired and green** — strict mypy + ruff + pytest (6 tests at the time)
- ✅ **S1.6 Implements D17 (config) and D22 (repo)** — recorded in commit `24a8f3b`

### S2 · External tools layer
- ✅ **S2.1 Shared HTTP client with timeouts + retry** — `tp_tools/_http.py`
- ✅ **S2.2 Geocoding** — `tp_tools/geocode.py` · 3 tests
- ✅ **S2.3 POI lookup (Overpass / OSM)** — `tp_tools/pois.py` · 6 tests
- ✅ **S2.4 Routing** — `tp_tools/routing.py` · 2 tests
- ✅ **S2.5 Weather** — `tp_tools/weather.py` · 1 test
- ✅ **S2.6 Typed payloads, not dicts** — `tp_tools/models.py`
- 🔄 **S2.7 Self-hosted Overpass** — `make downv-overpass` kept deliberately separate
  - ⏸️ S2.7.1 OSM import is a 2–4 h job; its volume must never be pruned (see 8.4.8.3)

### S3 · Retrieval / RAG
- ✅ **S3.1 Corpus construction** — `tp_retrieval/corpus.py`
- ✅ **S3.2 Embedder behind an interface** — `tp_retrieval/embedder.py` (D5, hardest to reverse)
- ✅ **S3.3 Vector store adapter (Qdrant)** — `tp_retrieval/vectorstore.py`
- ✅ **S3.4 Ingestion pipeline** — `tp_retrieval/ingest.py`, `make ingest`
- ✅ **S3.5 Retrieval + reranking** — `retrieve.py`, `rerank.py` · 6 tests
- 🔄 **S3.6 Operational hazard documented** — index and query embedder must match
  - 🔄 S3.6.1 A mismatch degrades RAG **silently**; no automated guard exists yet

### S4 · LLM gateway + tiering
- ✅ **S4.1 Provider enum + tiers** — `tp_core/llm/types.py` (CHEAP / MID / FRONTIER)
- ✅ **S4.2 Model catalogue per tier** — `llm/models.py` (`TIER_ROUTING`) · 3 tests
- ✅ **S4.3 Provider adapters** — `llm/providers.py` (Groq, OpenAI, Anthropic)
- ✅ **S4.4 Gateway with failover + token/cost capture** — `llm/gateway.py` · 5 tests
- ✅ **S4.5 Transient vs permanent failure split** — a 4xx is our bug, not the venue's

### S5 · Agent graph
- ✅ **S5.1 Graph state** — `tp_agents/state.py`
- ✅ **S5.2 Nodes** — `tp_agents/nodes.py` (retrieve -> ground -> draft)
- ✅ **S5.3 Prompts as code, versioned** — `tp_agents/prompts.py`
- ✅ **S5.4 Structured output schemas** — `tp_agents/schemas.py` (`Itinerary`, `TripItinerary`)
- ✅ **S5.5 Graph assembly** — `tp_agents/graph.py::build_planner_graph` · 10 tests

### S6 · Critic + corrective loop
- ✅ **S6.1 Critic pass over the drafted itinerary** — `tp_agents/critic.py` · 2 tests
- ✅ **S6.2 Bounded correction cycles** — a loop that cannot run away
- ✅ **S6.3 Verified live** — the Kyoto run took **1 critic correction** (see 8.5.4)

### S7 · API surface
- ✅ **S7.1 FastAPI app** — `apps/api/src/tp_api/main.py`
- ✅ **S7.2 Plan / run / stream endpoints** — 16 tests in `apps/api/tests/test_api.py`
- ✅ **S7.3 Container** — `apps/api/Dockerfile`
- ✅ **S7.4 Health and readiness mean different things**

### S8 · Multi-city coordinator
- ✅ **S8.1 Coordinator fans out per city, then reconciles** — `tp_agents/coordinator.py`
- ✅ **S8.2 Per-city worker reuses the single-city graph** — no second implementation
- ✅ **S8.3 Trip-level schema** — `TripItinerary` · 2 tests

### S9 · Async execution — dispatch · checkpointer · SSE
- ✅ **S9.1 Celery app + Redis broker** — `tp_core/celery.py` (D11)
- ✅ **S9.2 Worker app** — `apps/worker/`, `make worker`
- ✅ **S9.3 Run registry + persistence** — `tp_core/runs.py` (5 tests), `tp_core/db.py`
- ✅ **S9.4 Graph checkpointer** — `tp_agents/checkpoint.py` · 3 tests
- ✅ **S9.5 Event bus** — `tp_core/events.py`
- ✅ **S9.6 SSE streaming to the browser** — `test_stream.py` · 2 tests
- ✅ **S9.7 Committed** — `ae1fda8`, includes S9c

### S10 · Caching + cost controls
- ✅ **S10.a Caching + retry** — `tp_core/cache.py` · 4 tests (D10)
- ✅ **S10.b Cap + kill-switch + budget gate** — `tp_core/control.py` (2), `test_cost.py` (2),
      `test_budget.py` (1)
  - ⏸️ S10.b.1 **Awaiting commit** — code landed, not yet committed

### S11 · Observability
- ✅ **S11.1 OpenTelemetry tracing** — `tp_core/tracing.py` · 4 tests
- ✅ **S11.2 Langfuse LLM tracing** — keys live in `.env`
- ✅ **S11.3 Prometheus metrics** — `tp_core/metrics.py` · 4 tests
- ✅ **S11.4 Prometheus + Grafana + Loki/Promtail** — `infra/observability/`
  - ✅ S11.4.1 `prometheus.yml` · `promtail.yml` · `grafana-datasources.yml`
  - ✅ S11.4.2 Dashboard — `infra/observability/dashboards/voyantra.json`
- ✅ **S11.5 Alerting** — `alerts.yaml` + `alertmanager.yml`
- ✅ **S11.6 Compose stack** — `docker-compose.observability.yml`, `make observability`

### S12 · Security + Auth0
- ✅ **S12.1 JWT verification** — `tp_core/auth.py` · 5 tests (D9)
- ✅ **S12.2 ACL enforced at retrieval, not after** — `tp_core/guard.py` · 4 tests
- ✅ **S12.3 PII redaction on the logging path**
- ✅ **S12.4 Prompt-injection suite** — `packages/agents/tests/test_injection.py` · 3 tests
- ✅ **S12.5 Rate limiting** — `tp_core/ratelimit.py` · 4 tests
- ✅ **S12.6 Supply-chain gates** — `make audit-deps` · `sast` · `secrets` · `licenses` · `audit`

### S13 · Next.js frontend (Streamlit retired)
- ✅ **S13.1 App Router skeleton** — `apps/web/src/app/layout.tsx`, `middleware.ts`
- ✅ **S13.2 Marketing surface** — 9 routes under `app/(marketing)/`
- ✅ **S13.3 Product surface** — 8 routes under `app/app/`
  - ✅ S13.3.1 `plan/` · `runs/[id]/` · `trips/` · `explore/` · `destinations/[slug]/`
  - ✅ S13.3.2 `settings/` · `profile/`
- ✅ **S13.4 Route handlers** — `api/plan`, `api/trip`, `api/runs/[id]`, `api/runs/[id]/stream`
- ✅ **S13.5 Auth** — Auth0 (`lib/auth0.ts`) + Google OAuth + a dev-login escape hatch
- ✅ **S13.6 Trace UI** — `components/app/trace-timeline.tsx` (+ component test)
- ✅ **S13.7 Map** — `components/app/map-view.tsx`, `lib/map.ts` (MapLibre)
- ✅ **S13.8 Live run streaming hook** — `hooks/use-run-stream.ts` (+ test)
- ✅ **S13.9 UI kit** — 10 primitives under `components/ui/`
- ✅ **S13.10 Vitest suite** — 7 test files across `lib/`, `hooks/`, `components/`
- ✅ **S13.11 Container** — `apps/web/Dockerfile`
- ✅ **S13.12 Streamlit demo retired from the shipping tree**

---

## PHASE 5 — Production hardening

- ✅ **5.1 Chaos tests** — `packages/agents/tests/test_chaos.py` · 3 tests
- ✅ **5.2 Backup + restore drill** — `scripts/backup_restore_drill.sh`
- ✅ **5.3 Load test path** — `make load`
- ✅ **5.4 Evaluation harness** — `packages/eval/`
  - ✅ 5.4.1 Golden set — `tp_eval/golden.py`
  - ✅ 5.4.2 Runner + CLI — `runner.py`, `cli.py`, `__main__.py`
  - ✅ 5.4.3 Metrics + LLM judge — `metrics.py`, `judge.py`, `ragas_judge.py`
  - ✅ 5.4.4 CI gate — `tp_eval/gate.py` · 6 tests
  - ✅ 5.4.5 Baseline recorded — `packages/eval/baselines/baseline-rag.json`
- ✅ **5.5 Degradation behaviour proven** — a partial itinerary rather than a 500

## PHASE 6 — Deployment

- ✅ **6.1 Docker Compose, split by concern**
  - ✅ 6.1.1 `docker-compose.data.yml` — Postgres, Redis, Qdrant, Overpass
  - ✅ 6.1.2 `docker-compose.app.yml` — api, worker, web
  - ✅ 6.1.3 `docker-compose.observability.yml`
  - ✅ 6.1.4 `docker-compose.gpu.yml` — added this session (see 8.4.1)
- ✅ **6.2 Local Kubernetes (kind)** — `scripts/kind-up.sh` / `kind-down.sh`, `infra/kind/`
  - 🔄 6.2.1 **Image drift unreconciled** — `.env` pins `v1.31.2`, the cluster runs `v1.31.6`
- ✅ **6.3 Helm chart** — `infra/helm/voyantra/templates/`, 11 templates
  - ✅ 6.3.1 Workloads — `api.yaml` · `worker.yaml` · `web.yaml`
  - ✅ 6.3.2 Data — `postgres.yaml` · `redis.yaml`
  - ✅ 6.3.3 Config + secrets — `configmap.yaml` · `secret.yaml` · `externalsecret.yaml`
  - ✅ 6.3.4 Identity — `serviceaccount.yaml` (IRSA)
- ✅ **6.4 Terraform / AWS** — `infra/terraform/`, 10 files
  - ✅ 6.4.1 Network — `vpc.tf`, plus providers / versions / variables / outputs
  - ✅ 6.4.2 Compute — `eks.tf`
  - ✅ 6.4.3 Data — `rds.tf` · `elasticache.tf`
  - ✅ 6.4.4 Registry — `ecr.tf`
  - ✅ 6.4.5 Identity — `irsa.tf`
  - ⏳ 6.4.6 **GPU node group + scale-to-zero** — not written
- ✅ **6.5 ArgoCD GitOps** — `infra/argocd/`
  - ✅ 6.5.1 `project.yaml` + `application-dev/staging/prod.yaml`
  - ⏸️ 6.5.2 **Cloud apply is user-run** — never executed from here
- ✅ **6.6 CI/CD** — `.github/workflows/`
  - ✅ 6.6.1 `ci.yml` — lint, types, tests
  - ✅ 6.6.2 `cd.yml` — build, push, deploy
  - ✅ 6.6.3 `promote.yml` — dev -> staging -> prod behind the eval gate

## PHASE 7 — Postmortem & portfolio writeup

- ✅ **7.1 Case study written** — `case-study.md`
- ✅ **7.2 Portfolio README** — `README2.md`; public `README.md` in tree
- ✅ **7.3 Screenshots captured** — `screenshots/`
- ✅ **7.4 Internal labels neutralised for publication** — commit `8187988`
- ✅ **7.5 Private planning notes untracked** — commits `02b19e5`, `c676002`, `3424619`

---

## PHASE 8 — Local inference venue + repo ergonomics *(this session)*

### 8.1 · Makefile restructure
- ✅ **8.1.1 Boxed section titles, then a documentation block, then the commands**
- ✅ **8.1.2 Every variable declared once, in a single section at the top**
- ✅ **8.1.3 Grew 196 -> 616 lines, 35 -> 58 targets, 13 boxed sections**
- ✅ **8.1.4 Engine / GPU-profile resolution block**
  - ✅ 8.1.4.1 `ENGINE=vllm|sglang|none` maps to profile + chain + what to stop
  - ✅ 8.1.4.2 An unknown value `$(error ...)`s instead of running the wrong thing
- ✅ **8.1.5 Independent `vllm-*` family** — `vllm-up` · `-down` · `-upv` · `-downv` · `-test`
- ✅ **8.1.6 Independent `sglang-*` family** — the same five, touching only SGLang
- ✅ **8.1.7 One-command full bring-up** — `make up-vllm` / `make up-sglang`
  - ✅ 8.1.7.1 image (pull if absent) -> container -> weights -> load -> **serve**
  - 📝 8.1.7.2 I claimed `up-with-engine` exporting `SERVING_CHAIN` made `ENGINE=`
        authoritative. **It had no consumer** — `docker-compose.app.yml` uses an explicit
        `environment:` allowlist, not `env_file`, so the var reached no container.
  - ✅ 8.1.7.3 **FIXED** — `ENGINE_URL_ENV` added per branch; the target now exports the
        engine URL alongside the chain, and `app.yml` names both under `environment:`
  - ⚠️ 8.1.7.4 **Ordering bug found and fixed** — the app was started BEFORE the engine,
        so its opening requests failed the local leg, tripped the breaker and were
        answered (and billed) by a hosted venue. Engine now comes up first.
- ✅ **8.1.8 Support targets** — `which-engine` · `engine-guide` · `webui` · `clean-models`
- ✅ **8.1.9 Benchmarks** — `bench-engine` · `bench-groq` · `bench-openai`
- ⚠️ **8.1.10 `.PHONY` kept on a single line** — the Bash tool mangles line continuations
- ✅ **8.1.11 Default engine is SGLang**
- 📝 **8.1.12 False "orphan targets" alarm was mine** — my checker's regex excluded `=`,
      and help strings contain `SERVING_CHAIN=...`. The instrument was wrong, not the system.

### 8.2 · `.env` / `.env.example` restructure
- ✅ **8.2.1 Confirmed a prior session had already restructured both** — 76 vars, 57 sections
  - 📝 8.2.1.1 A stale `Read` showed 239 lines / 74 vars / 26 trailing comments; disk had 490
        lines. One command from overwriting prior work. **Rule adopted: verify with bash.**
- ✅ **8.2.2 Added a `LOCAL INFERENCE` section** — engine, URLs, models, chains, breaker
- ✅ **8.2.3 Added inference-tier ports** — vLLM 3019 · SGLang 3020 · WebUI 3021
- ✅ **8.2.4 Both files now 92 vars, zero drift between them**
- ✅ **8.2.5 Zero trailing comments** — `VAR=x  # note` parses the comment into the value
- ✅ **8.2.6 Real secrets preserved byte-exactly and never sent anywhere**
- ✅ **8.2.7 `SERVING_CHAIN` ships EMPTY** — legacy routing until you opt in

### 8.3 · Serving chain + circuit breaker
- ✅ **8.3.1 Chain grammar + parser** — `tp_core/llm/venues.py`
  - ✅ 8.3.1.1 `local` · `local-vllm` · `local-sglang` · `groq` · `openai` · `anthropic`
  - ✅ 8.3.1.2 `venue:model` overrides the model for that call-point
  - ✅ 8.3.1.3 A bare `sglang` is **rejected at startup**, and the error names the fix
  - ✅ 8.3.1.4 Duplicate venue, unknown venue and empty chain each raise `ConfigError`
  - ✅ 8.3.1.5 A list, not priority numbers — numbers split identity from order
- ✅ **8.3.2 Two-level configuration (D24 as amended)**
  - ✅ 8.3.2.1 `SERVING_CHAIN` — one baseline order for every tier
  - ✅ 8.3.2.2 `CHAIN_CHEAP` / `CHAIN_MID` / `CHAIN_FRONTIER` override per tier
  - ✅ 8.3.2.3 `raw_chain_for_tier()` — narrow beats broad; empty means "unset", not "empty"
  - ✅ 8.3.2.4 Default leaves FRONTIER hosted — one loaded 7B cannot be three tiers
  - 📝 8.3.2.5 I first built a single chain against an approved per-tier design, because I
        coded before re-reading D24. Resolved as the hybrid above, at your call.
- ✅ **8.3.3 Circuit breaker** — `tp_core/llm/circuit.py`
  - ✅ 8.3.3.1 CLOSED / OPEN / HALF_OPEN; threshold 3, cooldown 30 s
  - ✅ 8.3.3.2 HALF_OPEN admits **exactly one** probe
  - ✅ 8.3.3.3 A 4xx does not count against a venue
  - ✅ 8.3.3.4 `snapshot()` reports every known leg, not only the one that moved
  - ⚠️ 8.3.3.5 **Clock bug found and fixed** — `snapshot()` mixed an injected clock with
        `time.monotonic()`, so a just-opened leg read half-open. Caught by a new test.
  - ✅ 8.3.3.6 Scope recorded as per-process, with the Redis trade-off written down
- ✅ **8.3.4 Local provider** — `LocalEngineProvider` in `llm/providers.py`
  - ✅ 8.3.4.1 `AsyncOpenAI(base_url=...)` — one adapter serves both engines
  - ✅ 8.3.4.2 `max_retries=0` — the chain retries, not the client
  - ✅ 8.3.4.3 `cost_usd=0.0` set explicitly (0.0 is a measurement, not a blank)
- ✅ **8.3.5 Gateway rework** — `llm/gateway.py`
  - ✅ 8.3.5.1 `chains: dict[Tier, list[ChainLeg]]` + `_resolve_chain(tier)`
  - ✅ 8.3.5.2 Precedence: per-tier -> baseline -> legacy `TIER_ROUTING`
  - ✅ 8.3.5.3 Breaker consulted before each leg; a leg with no key is skipped
        **with a warning naming it** — never a silent downgrade
  - ✅ 8.3.5.4 **Backward compatible by construction** — an empty chain reproduces
        legacy routing exactly
- ✅ **8.3.6 Settings** — `serving_chain` · `serving_engine` · per-tier chains · URLs ·
      models · `circuit_failure_threshold` · `circuit_cooldown_seconds`
- ✅ **8.3.7 Tests** — `packages/core/tests/test_llm_local_venues.py`, 21 test functions
  - ✅ 8.3.7.1 Includes a test pinning that a 7B never reaches FRONTIER

### 8.4 · GPU venue infrastructure
- ⚠️ **8.4.0 The extension was never wired to any container** — found by verification,
      not by a test. `docker-compose.app.yml` passes an explicit `environment:` allowlist;
      none of `SERVING_*`, `CHAIN_*`, `VLLM_URL`, `SGLANG_URL`, `CIRCUIT_*` was in it.
  - ✅ 8.4.0.1 Proven inside both containers — every one of them read empty
  - 📝 8.4.0.2 This is why the app kept working: an empty chain falls back to legacy
        `TIER_ROUTING`, so the invalid `SERVING_CHAIN=sglang,...` in `.env` never reached
        a container and never raised. **Luck, not design.**
  - ✅ 8.4.0.3 **FIXED** — 14 vars added to `environment:` on api **and** worker;
        `compose config` validates; ruff clean and 150 passed afterwards
- ✅ **8.4.1 `docker-compose.gpu.yml`**
  - ✅ 8.4.1.1 vLLM :3019 (`gpu-vllm`) · SGLang :3020 (`gpu-sglang`) · WebUI :3021 (`webui`)
  - ✅ 8.4.1.2 Shared `tp_hf_cache` volume — one 5.5 GB download serves either engine
  - ✅ 8.4.1.3 `shm_size: 8gb`, `ipc: host`
  - ✅ 8.4.1.4 Healthcheck polls the engine's own `/health`, `start_period: 900s`
        — `--wait` alone returns while 5.5 GB of weights are still loading
- ✅ **8.4.2 Preflight** — `scripts/engine_preflight.sh` · **run, works**
  - ✅ 8.4.2.1 Sizes need as `weights x1.4 + 1.5 GB`; refuses in ~2 s rather than exit 137
        after twenty minutes
  - ✅ 8.4.2.2 Names the container holding the card and prints the command to stop it
- ✅ **8.4.3 Failure diagnostic** — `scripts/engine_failed.sh`
  - ✅ 8.4.3.1 Branches on **real** container state: running / 137 / crash / gone
  - ✅ 8.4.3.2 Refuses to guess — the obvious "it is still loading" version misleads
        exactly when it matters
- ✅ **8.4.4 Benchmark harness** — `scripts/bench_venue.py` · **RUN, 5/5 succeeded**
  - ✅ 8.4.4.1 TTFT p50 **50 ms** / p95 559 ms · TPOT p50 **15.2 ms** · **60.8 tok/s**
  - ✅ 8.4.4.2 Warmup discard justified by the data: warmup TTFT 246 ms, run-1 559 ms,
        then ~50 ms steady — the cold request is a different machine
  - ⚠️ 8.4.4.3 `make bench-groq` **fails 404** — see 8.8
- ✅ **8.4.5 Hardware recon** — RTX 3060 12 GB, cc 8.6; passthrough verified inside a container
- ✅ **8.4.6 Model chosen** — `Qwen/Qwen2.5-7B-Instruct-AWQ`, INT4, ~5.5 GB, ungated
- ✅ **8.4.7 Both engine images confirmed already pulled** — vLLM 30.8 GB, SGLang 47 GB
- ✅ **8.4.8 Disk reclaim, reviewed line by line before deleting**
  - ✅ 8.4.8.1 Docker internals + odds (1.13 GB) · stale p61 tags (1.80 GB) · dupes (8.14 GB)
  - ⚠️ 8.4.8.2 Prevented deletion of the 30.8 GB vLLM image that read as "unused"
  - ⚠️ 8.4.8.3 Prevented `docker volume prune` — **547 of 565** volumes read as dangling,
        including the 2–4 h OSM import, because `compose down` removes containers
  - 📝 8.4.8.4 I first claimed ~11 GB reclaimed; actual was **6.8 GB** — `docker images`
        counts shared base layers once per image
  - ⏳ 8.4.8.5 VHDX compact, to hand the space back to Windows — not done

### 8.5 · Venue on the response contract + metrics
- ✅ **8.5.1 Metrics** — `tp_core/metrics.py`
  - ✅ 8.5.1.1 `LLM_TOKENS` · `LLM_COST` counters
  - ✅ 8.5.1.2 `CIRCUIT_STATE` gauge, `multiprocess_mode="mostrecent"`
  - ✅ 8.5.1.3 Labels bounded to enum values — no unbounded cardinality
  - ✅ 8.5.1.4 `record_venue_usage()` + `record_circuit()`
- ✅ **8.5.2 `venues` added to the schemas** — `Itinerary` and `TripItinerary`
- ✅ **8.5.3 Accumulated along the whole path**
  - ✅ 8.5.3.1 `nodes.py` — union of this response's venue with the prior set
  - ✅ 8.5.3.2 `critic.py` — the critic's own venue merged in
  - ✅ 8.5.3.3 `coordinator.py` — union across every city
  - ✅ 8.5.3.4 Rides the existing `result` JSON column — **no DB migration**
- ✅ **8.5.4 Proven end-to-end on a real run**
  - ✅ 8.5.4.1 Kyoto, 1 day, 5 POIs, $0.00656, 1 critic correction
  - ✅ 8.5.4.2 `venues: ['openai']` survives `model_dump(mode="json")`

### 8.6 · Documentation
- ✅ **8.6.1 `docs/DECISION_LOG_LOCAL_INFERENCE.md`** — 299 -> 441 lines, dated amendments
  - ✅ 8.6.1.1 D24 recorded as the **hybrid actually built**, not as first drafted
  - ✅ 8.6.1.2 An explicit verified-vs-unverified table
- ✅ **8.6.2 `docs/gpu-venue.md`** — the bring-up runbook
  - ✅ 8.6.2.1 "A liveness check is not a capacity check"
  - ✅ 8.6.2.2 "Declared is not working"
  - ✅ 8.6.2.3 vLLM `--gpu-memory-utilization` (fraction of **free**) vs SGLang
        `--mem-fraction-static` (fraction of **total**) — not the same knob
  - ✅ 8.6.2.4 One engine at a time: 0.80 + 0.70 is 150% of the card, and it **wedges**
        at "Starting to load model" rather than failing fast
  - ✅ 8.6.2.5 Never `docker volume prune`
  - ✅ 8.6.2.6 The first download must not be interrupted — `huggingface_hub` does not resume
  - ✅ 8.6.2.7 `make webui` is deliberately the unguarded path, so engine quality and
        product quality are judged separately
- ✅ **8.6.3 `docs/DECISION_LOG.md` left untouched** — verified

### 8.7 · Bring-up and measurement
- ✅ **8.7.1 Engine STARTED and PROVEN GENERATING** — healthy in 360 s; `/v1/chat/completions`
      returned real text; `max_total_num_tokens=11881`, 10406 MiB used / 1708 MiB free.
      Original blocker note follows:
- ✅ **8.7.1-orig Start an engine and prove it generates** — **UNBLOCKED**:
      `p5-medical-chatbot-sglang-1` exited 30 h ago; the card is free. Engine started and
      is loading; not yet proven to generate.
  - ✅ 8.7.1.1 Preflight **correctly refused** — 8980 MiB free vs a 9200 MiB heuristic.
        The check did its job; it was not bypassed blindly.
  - ✅ 8.7.1.2 `SGLANG_MEM_FRACTION` 0.70 -> **0.55** to leave ~1.4 GB desktop headroom,
        because the 3055 MiB in use is ordinary Windows desktop, not a stale container
  - ⚠️ 8.7.1.3 SGLang additionally reserves **1024 MiB for CUDA IPC**, which the
        preflight heuristic does not model — first number to lower if it OOMs
- ✅ **8.7.2 `make bench-engine` ran** — TTFT p50 50 ms · TPOT p50 15.2 ms · 60.8 tok/s
- ✅ **8.7.3 Chain flipped and confirmed** — `venues: ['local-sglang']` at $0.00 on a real plan
- ✅ **8.7.4 `scripts/ensure_weights.sh`** — WRITTEN and RUNNING, prompted by a real failure
  - ⚠️ 8.7.4.1 First cold start **stalled**: 0.87 GB of 5.5 GB, then **zero bytes for 6
        minutes** while the container sat `unhealthy` and kept holding the GPU.
        Unauthenticated HF downloads are rate-limited and hang without erroring.
  - ✅ 8.7.4.2 Weights now fetched in a throwaway container with **no `--gpus`** — a
        stalled download must not park the card
  - ✅ 8.7.4.3 Stall detection by sampling cache growth; a zero-growth window is treated
        as death and retried. Safe because `.incomplete` blobs resume.
  - ✅ 8.7.4.4 Completion verified by **content** (`*.safetensors` present), not exit status
  - ⚠️ 8.7.4.5 **`start_period: 900s` is too short** — it covers a cold *load*, not a cold
        *download* on a rate-limited link. `make sglang-up`'s `--wait-timeout 900` would
        have declared failure on a download that was still alive. Not yet fixed.

---

## GATE — current state

- ✅ **G.1 `ruff`** — All checks passed
  - ⚠️ G.1.1 Fixed: `E741` ambiguous name `l` (twice) -> `leg`; line-too-long wrapped
- ✅ **G.2 `mypy --strict`** — clean
  - ⚠️ G.2.1 Fixed: `override` typed `str` but assigned `str | None`
- ✅ **G.3 `pytest`** — **150 passed**; baseline 128 -> +22, zero regressions
- ✅ **G.4 139 test functions across 33 files** (parametrisation expands to 150 cases)
- ✅ **G.5 Frontend vitest suite green** — 7 files

## GIT — prepared, never run

- ✅ **N.1 Standing constraint honoured** — no `git add` / `commit` / `push` / GitHub op
- ⏳ **N.2 Extend the prepared `git add` list to this round**
  - ⏳ N.2.1 `Makefile` · `.env.example` · `docker-compose.gpu.yml`
  - ⏳ N.2.2 `packages/core/src/tp_core/llm/{venues,circuit,providers,gateway}.py`
  - ⏳ N.2.3 `packages/core/src/tp_core/{settings,metrics}.py`
  - ⏳ N.2.4 `packages/agents/src/tp_agents/{schemas,nodes,critic,coordinator}.py`
  - ⏳ N.2.5 `packages/core/tests/test_llm_local_venues.py`
  - ⏳ N.2.6 `scripts/{engine_preflight.sh,engine_failed.sh,bench_venue.py}`
  - ⏳ N.2.7 `docs/{DECISION_LOG_LOCAL_INFERENCE.md,gpu-venue.md}` · `update_todos.md`
  - ⏳ N.2.8 Still uncommitted from earlier — **S10.b**

## NEXT — the moment the GPU is free

- ✅ **X.1** engine started, healthy in 360 s
- 🔄 **X.2** the app WAS confirmed to see its venue (container env + `venues` on the response),
      but `make which-engine` itself was never executed
- ✅ **X.3** proved it GENERATES — real text returned, `finish_reason: stop`
- 🔄 **X.4** `make bench-engine` ran; `make bench-groq` 404'd on the retired model and has
      NOT been re-run since the Groq rung was repaired — the side-by-side is still missing
- ✅ **X.5** confirmed — `venues: ['local-sglang']`, cost $0.002487 -> $0.00
- ✅ **X.6** measured table written into `docs/gpu-venue.md` §7


---

## 8.8 · PROVEN END-TO-END *(2026-09-07)*

- ✅ **8.8.1 The whole chain works** — same Kyoto plan, before vs after
  - ✅ 8.8.1.1 `venues: ['openai']` -> **`venues: ['local-sglang']`**
  - ✅ 8.8.1.2 cost `$0.002487` -> **`$0.00`**
  - ✅ 8.8.1.3 17 s vs 15 s — local costs ~2 s of wall clock, not minutes
  - ✅ 8.8.1.4 Worker resolves the engine by service DNS (`http://sglang:30000/v1`),
        confirming the shared-compose-project assumption
- ✅ **8.8.2 Weights staged** — 6202 MB cached, both shards symlinked, zero `.incomplete`
  - ⚠️ 8.8.2.1 **Xet was the real blocker** — 0 MB/120 s with it, 21 MB/90 s without.
        A token changed nothing (0.19 -> 0.23 MB/s); with Xet off it ran at **3.6 MB/s**.
  - 📝 8.8.2.2 I recommended the HF token as the fix. It was not the cause. I quoted
        ETAs of 7 h then 2 h; the real download took ~20 min once Xet was disabled.
  - ⚠️ 8.8.2.3 `.env` had **two** `HF_TOKEN=` lines; the empty later one silently won.
        Caught only because the script announces AUTHENTICATED/ANONYMOUS out loud.
- ⚠️ **8.8.3 THE GROQ LEG IS DEAD** — found by running the benchmark, not by a test
  - ✅ 8.8.3.1 `llama-3.1-8b-instant` and `llama-3.3-70b-versatile` both return **404**;
        Groq now serves `openai/gpt-oss-*` and `qwen/qwen3.*`
  - ✅ 8.8.3.2 Both are in `TIER_ROUTING` for CHEAP, MID and FRONTIER
  - 📝 8.8.3.3 This explains the pre-change run reading `venues: ['openai']` when D4
        specifies **Groq first**: the free leg was 404ing and traffic fell silently to
        the paid one. The app has been paying OpenAI for work Groq was meant to do.
  - ⏳ 8.8.3.4 **NOT FIXED** — choosing a replacement model is a D4 decision (quality
        and cost), not a typo fix. Needs a call before editing `TIER_ROUTING`.
- ✅ **8.8.4 Preflight passed on its own merits** — 9270 MiB free vs 9200 needed;
      no `SKIP_MEM_CHECK` override was used in the end
- 📝 **8.8.5 My throughput estimate was too pessimistic** — I predicted 25-40 tok/s and
      a 40-60 s itinerary. Actual: **60.8 tok/s** and **17 s**. The latency worry that
      prompted relaxing the p95 target was unfounded; no threshold needs moving.


## 8.9 · EVAL GATE AGAINST THE LOCAL ENGINE *(2026-09-07)*

- ✅ **8.9.1 Generation local, judge hosted — the confound avoided**
  - ✅ 8.9.1.1 Tiers separate cleanly: MID=planning, FRONTIER=critic, CHEAP=**judge only**
  - ✅ 8.9.1.2 `CHAIN_MID=local-sglang CHAIN_CHEAP=openai` — the 7B never grades itself.
        This is the per-tier override from D24 earning its existence.
  - ✅ 8.9.1.3 Host runs need `SGLANG_URL=http://localhost:3020/v1`; the in-network name
        in `.env` is for containers only
- ✅ **8.9.2 Fixtures run PASSES the gate** vs `baseline.json` — all 8 checks green
- ✅ **8.9.3 Retrieval run, 5 replicates of the same config**

  | run | faithfulness | relevance | gate |
  |---|---|---|---|
  | 1 | **0.8571** | 0.9286 | **FAIL** |
  | 2 | 1.0 | 1.0 | PASS |
  | 3 | 1.0 | 0.8714 | PASS |
  | 4 | 1.0 | 1.0 | PASS |
  | 5 | 1.0 | 1.0 | PASS |

  - ✅ 8.9.3.1 4 of 5 PASS. The one failure was a single invented POI
        ("the nearby park") in `kyoto-temples`
  - ✅ 8.9.3.2 `grounded_rate` 0.8571 and `mean_poi_coverage` 1.0 on **every** run —
        identical to the hosted baseline
  - ✅ 8.9.3.3 `mean_relevance` 0.87 -> 0.93-1.00, i.e. the 7B scored **above** the
        hosted baseline on relevance
  - ✅ 8.9.3.4 Cost per itinerary `$0.0015` -> **`$0.00`**
- 📝 **8.9.4 I nearly claimed the hosted critic caught the hallucination. It did not.**
  - ✅ 8.9.4.1 Provider census proved it: 7 calls, all `tier=mid`, **zero `tier=frontier`**
  - ✅ 8.9.4.2 `runner.py:79` calls `compose_node` **directly** — the critic is not in
        the eval path at all, by design, so the eval scores the compose seam alone
  - ✅ 8.9.4.3 My "full-local vs hybrid" comparison was therefore meaningless: both
        configs are identical where the eval actually reaches. The difference was
        sampling variance, and I would have reported a causal story that did not exist.
- ⚠️ **8.9.5 The gate is one-hallucination-fragile at n=7**
  - ✅ 8.9.5.1 Threshold 0.95 vs a metric that can only take values k/7 -> the nearest
        passing value below 1.0 is 0.857, which fails. The gate is effectively
        "zero hallucinations allowed", and nobody chose that.
  - ⏳ 8.9.5.2 **NOT FIXED** — either widen the golden set or state the intent
        explicitly. A decision, not a tweak.
  - ✅ 8.9.5.3 The eval measures compose WITHOUT the critic, so it is a **lower bound**
        on production quality; the real corrective loop is unmeasured by it
- ✅ **8.9.6 VERDICT: the 7B is viable for planning.** Grounding and coverage match the
      hosted baseline, relevance beats it, cost goes to zero. The open risk is occasional
      POI invention, which is exactly what the critic exists to catch — and exactly what
      this eval does not exercise.


## 8.10 · FAILOVER CHAIN PROVEN END-TO-END *(2026-09-07)*

Order under test: **local-sglang -> groq -> openai**, exercised through the real
`POST /plan` endpoint, not a unit test.

| # | condition | venue that answered | cost | result |
|---|---|---|---|---|
| 1 | engine up | `['local-sglang']` | **$0.00** | 5 items ✅ |
| 2 | engine **stopped** | `['groq']` | $0.000232 | 5 items ✅ |
| 3 | engine stopped **+ no Groq key** | `['openai']` | $0.002698 | 5 items ✅ |

- ✅ **8.10.1 Every leg answers, and the price rises exactly as designed** — free, then
      cheap, then paid. Cost is the tripwire: $0.00 -> $0.0027 is how a dead engine
      announces itself.
- ✅ **8.10.2 No request ever failed** — all three degraded, none errored
- ✅ **8.10.3 The skip is LOUD, not silent** — leg 3 logged
      `llm_chain_leg_skipped tier=mid venues=groq` and the same for `tier=frontier`
- ✅ **8.10.4 Restored** — engine back up, key back, `['local-sglang']` at $0.00

### ⚠️ 8.10.5 The Groq rung had to be repaired first — it could not have worked
- ✅ 8.10.5.1 `llama-3.1-8b-instant` and `llama-3.3-70b-versatile` both **404** (retired)
- ✅ 8.10.5.2 Of the four models Groq now serves, only **`qwen/qwen3.8-27b`** is usable:
      `openai/gpt-oss-20b` and `-120b` return **empty `message.content`** (reasoning
      models, 96 tokens spent into a field the app never reads) and `qwen3.6-27b` leaks
      `<think>` into the content. Both would break structured output.
- ✅ 8.10.5.3 Routed for CHEAP, MID and FRONTIER; priced at an **estimated** (0.29, 0.59)
      because an unpriced model reports $0 and under-reports spend
- ✅ 8.10.5.4 Gate still green after the change: ruff clean, **150 passed**
- ⏳ 8.10.5.5 Verify the price against Groq's pricing page — estimate, not fact
- 📝 8.10.5.6 My verification assertion (`"llama-3." not in source`) failed on my own
      explanatory comment naming the retired models. The file was never written, so the
      atomicity held — but that is the third time this session the measuring instrument
      was wrong rather than the system.


---

# PHASE 9 — Makefile composition · .env completion · Grafana rebuild
*(planned 2026-09-07, before any code was written)*

## T1 · Makefile — compose aggregates from primitives

- ✅ **T1.0 Survey done** — 5 `DC_*` vars; `data`/`app`/`observability`/`full`/`up`/`down`/
      `downv`/`upv`/`bootstrap` each inline their own `docker compose` call
- ✅ **T1.0.1 Root cause named** — `DC_APP := -f data.yml -f app.yml`. The app tier is
      defined by a FILE SET that includes the data tier, so `make app` cannot mean "only
      the app". Scoping by file is the bug; scoping by SERVICE is the fix.
- ✅ **T1.1 Replace file-set scoping with service-set scoping**
  - ✅ T1.1.1 One canonical `DC` (all three -f flags) so compose always resolves
        `depends_on` — `app.yml` names `db`/`redis`, so an app-only file set cannot parse
  - ✅ T1.1.2 `SVC_DATA := db redis qdrant overpass`
  - ✅ T1.1.3 `SVC_APP := api worker web`
  - ✅ T1.1.4 `SVC_OBS := jaeger flower redisinsight prometheus grafana loki promtail
        alertmanager langfuse-*` (14 services)
  - ✅ T1.1.5 Retire `DC_APP` / `DC_OBS` / `DC_FULL`; keep `DC_GPU` (separate profile file)
- ✅ **T1.2 Primitive targets — one per tier, the only place a compose verb appears**
  - ✅ T1.2.1 `up-data` · `up-app` · `up-obs`
  - ✅ T1.2.2 `down-compose` · volume wipe helper
  - ✅ T1.2.3 `make app` uses `--no-deps` so it means ONLY api+worker+web, with a
        precondition that names the missing tier instead of crash-looping
- ✅ **T1.3 Aggregates call primitives, never a raw compose verb**
  - ✅ T1.3.1 `up` = up-engine -> up-data -> up-app -> up-obs -> infra
  - ✅ T1.3.2 `full` = up-data -> up-app -> up-obs (no kind, no engine)
  - ✅ T1.3.3 `bootstrap` = up-data -> up-app -> migrate -> seed
  - ✅ T1.3.4 `upv` = downv -> up-data -> up-app -> migrate -> seed -> up-obs
  - ✅ T1.3.5 `down` = down-compose -> infra-down · `downv` = down-compose -> wipe
- ✅ **T1.4 `make up` defaults to SGLang** — `ENGINE ?= sglang`, engine starts BEFORE the app
- ✅ **T1.5 Verify every path** — `make -n` for up/down/upv/downv/app/data/observability and
      up with ENGINE=vllm|both|none; assert no target starts a tier it should not

## T2 · .env — audit, then wire what is real

- ✅ **T2.0 Survey done** — 93 keys in `.env`; `settings.py` reads 29 fields
- ✅ **T2.1 Classify every candidate from the P5 reference into three buckets**
  - ✅ T2.1.1 **A — add now, already wired**: a variable the code reads today
  - ✅ T2.1.2 **B — needs code**: valuable, but adding the line alone is decoration
  - ✅ T2.1.3 **C — does not apply**: P5-only (ml-service, SQS/LocalStack, Clerk,
        semantic cache, ONNX backends)
  - ✅ T2.1.4 Present the classification and get a decision BEFORE writing anything
- ✅ **T2.2 Candidate bucket-B work, highest value first** (proposal, not yet approved)
  - ✅ T2.2.1 `LLM_ENABLED` floor + `DAILY_SPEND_LIMIT_USD` + `SPEND_SOFT_ALERT_RATIO` —
        complements the existing Redis `planning:enabled` switch with a static operator floor
  - ✅ T2.2.2 `RATE_LIMIT_PER_DAY`, `RATE_LIMIT_IP_PER_MIN`, `TRUSTED_PROXY_HOPS` — today
        only `RATE_LIMIT_PER_MIN` exists, so a rotating cookie multiplies the allowance
  - ✅ T2.2.3 `RETRIEVAL_TOP_K` / `RERANK_TOP_K` — currently hardcoded in `tp_retrieval`
  - ✅ T2.2.4 `PROMPT_VERSION` / `CORPUS_VERSION` / `INDEX_VERSION` — cache invalidation by
        version key instead of flushing Redis by hand
  - ✅ T2.2.5 Postgres + Redis circuit breakers, reusing the existing `CircuitBreaker`
- ✅ **T2.3 Invariants that must still hold afterwards**
  - ✅ T2.3.1 Zero trailing comments
  - ✅ T2.3.2 **Zero duplicate keys** — add a structural check; a second empty `HF_TOKEN=`
        silently won once already
  - ✅ T2.3.3 Zero key drift between `.env` and `.env.example`
  - ✅ T2.3.4 Every existing secret preserved byte-exactly, never printed
  - ✅ T2.3.5 Section shape: boxed title -> docs indexed by variable -> clean assignment block

## T3 · Grafana — instrument first, then chart

- ✅ **T3.0 Survey done** — dashboard has 10 panels; `metrics.py` emits **9** series
- ⚠️ **T3.0.1 The blocking finding**: the requested dashboard needs metrics that do not
      exist. `metrics.py` has no stage latency, no cache hit/miss, no rate-limit events, no
      outcome kind, no error type, no per-venue latency, no retrieval counts. Charting them
      now would produce panels that say `No data` **forever**, which is indistinguishable
      from "healthy and quiet" — the same declared-vs-working trap that hid the dead Groq leg.
- ✅ **T3.1 Add the missing instrumentation (additive, no behaviour change)**
  - ✅ T3.1.1 `tp_stage_duration_seconds{stage}` — geocode · gather · compose · critic
  - ✅ T3.1.2 `tp_venue_latency_seconds{provider}` — per-venue, so local vs hosted is visible
  - ✅ T3.1.3 `tp_cache_events{tool,result}` — hit/miss per tool
  - ✅ T3.1.4 `tp_itinerary_outcome{kind}` — grounded · degraded · not_found
  - ✅ T3.1.5 `tp_rate_limit_events{scope,outcome}`
  - ✅ T3.1.6 `tp_errors{type}`
  - ✅ T3.1.7 `tp_retrieval_results` — POIs returned per query
  - ✅ T3.1.8 Labels bounded to enums; counters keep the `_total` convention
- ✅ **T3.2 Rebuild the dashboard in question-titled sections**
  - ✅ T3.2.1 Headline row — latency p50/p95 vs NFR, request p95, cost/request, req/sec, 5xx
  - ✅ T3.2.2 Per-venue rows: `local-sglang` · `local-vllm` · `groq` · `openai`
  - ✅ T3.2.3 A venue with no traffic must read **"not served since restart"**, never `No data`
  - ✅ T3.2.4 "Is the product refusing what it must?" — outcome kinds, degraded answers,
        which declines cost money, silent quality degradation
  - ✅ T3.2.5 "Where does the time actually go?" — stage latency, end-to-end by outcome,
        cache hit rate, cache events/sec, tokens/sec by venue and direction
  - ✅ T3.2.6 "Are the parts underneath still healthy?" — venue breakers, infra breakers,
        rate limiting by scope, errors by type, Celery queue depth, retrieval counts
  - ✅ T3.2.7 Every panel carries a `description`: what it measures, and what bad looks like
- ✅ **T3.3 No dead panels** — cross-check every query against `metrics.py`; publish the list
      of which panels are backed by pre-existing metrics vs new instrumentation
- ✅ **T3.4 Verify by LOADING it** — confirm Grafana parses the JSON and panels render;
      a valid file is not a working dashboard

## Gate after every task
- ✅ `ruff` clean · `mypy --strict` clean on 59 files · `pytest` **169 passed**
- ✅ App still serves — verified after T1, T2 and T3


---

## T1 · RESULT — verified 2026-09-07

✅ **Done.** `DC_APP` / `DC_OBS` / `DC_FULL` / `DC_DATA` retired; zero live usages remain.

| target | resolves to |
|---|---|
| `make data` | `up-data` -> `db redis qdrant overpass`, then `--wait` on `db redis qdrant` |
| `make app` | `up-app` -> precondition check, then `--no-deps api worker web` |
| `make observability` | `up-obs` -> the 14 observability services |
| `make full` | `up-data up-app up-obs` |
| `make bootstrap` | `up-data up-app` -> migrate -> seed |
| `make up` | `up-engine` -> `up-data up-app up-obs` -> `infra` |
| `make upv` | `down-compose` -> `up-data up-app` -> migrate -> seed -> `up-obs` |
| `make down` | `down-compose` -> `infra-down` |
| `make downv` | `down-compose` -> volume wipe |

- ✅ **T1.R1 The fix is PROVEN, not asserted.** `db` `StartedAt` was
      `2026-09-07T04:52:56.263018442Z` both before and immediately after `make app` —
      byte-identical, so the app tier genuinely no longer restarts the data tier.
- ✅ **T1.R2 App still serves after the refactor** — a real `POST /plan` returned
      5 items. With the engine down it failed over to `venues: ['groq']` at $0.000223,
      which also re-confirms the repaired Groq rung.
- ✅ **T1.R3 All four `ENGINE` values still resolve** — sglang / vllm / both / none, each
      exporting the right chain and URL into the composed `up-data up-app up-obs`.
- ⚠️ **T1.R4 Two guard bugs of mine, caught by the guards themselves.** The
      idempotence check tested for any MENTION of `SVC_DATA`, and the completeness check
      for any mention of `DC_APP` — both of which my own new explanatory comments contain.
      Nothing was written either time (assert-before-write held). Fixed to match
      `^SVC_DATA\s+:=` and `\$\(DC_...\)` — assignments and usages, not prose.
      Third time this session the measuring instrument was wrong rather than the system.
- 📝 **T1.R5 Inconsistency now visible and NOT yet resolved**: `.env` still carries
      `SERVING_CHAIN=local-sglang,groq,openai` while the Makefile chains drop `openai`.
      `.env` is what applies when the stack starts WITHOUT make (bare `docker compose up`,
      a container restart), so the two disagree on whether a paid last-resort leg exists.
      Deliberately left for T2 rather than changed silently.

---

## T2 · DETAILED PLAN — audited against the code, 2026-09-07

### T2.A · Audit result — what the code actually does today

- ✅ **T2.A.1 Kill switch EXISTS but has no floor** — `control.planning_enabled()` reads the
      Redis key `planning:enabled`, fail-open. There is no static setting, so anyone with
      `redis-cli` can turn generation back on. An operator's decision does not outrank a
      runtime flag, which is backwards.
- ✅ **T2.A.2 Cost cap is PER-ITINERARY only** — `graph.py:33` compares run cost against
      `max_cost_usd` (0.30). Nothing accumulates spend across runs, so "this month went to
      the paid leg because the GPU was down" is unanswerable — the exact question the
      serving chain exists to make answerable.
- ✅ **T2.A.3 Rate limiting is ONE window, ONE scope** — `allow_request(tenant, limit,
      window_s=60)`. No daily budget, no per-IP scope. A client that rotates its session
      cookie multiplies its allowance by however many cookies it cares to mint.
- ✅ **T2.A.4 No client-IP extraction anywhere** — nothing reads `X-Forwarded-For`, so a
      per-IP limit cannot be added without deciding how many proxy hops to trust.
- ✅ **T2.A.5 Retrieval depth is HARDCODED** — `Retriever.retrieve(..., k=20, top_n=8)`.
      Tuning recall/latency today means editing Python.
- ✅ **T2.A.6 Cache keys carry NO version** — `cache_aside(key, ttl, ...)` with fixed TTLs
      (geocode 30d, POIs 7d, weather 6h, route 7d, embed 30d). Invalidating after a prompt
      or corpus change means flushing Redis by hand, which also throws away everything else.
- ⚠️ **T2.A.7 `CircuitBreaker` is typed to `Provider`** — `_legs: dict[Provider, _Leg]`.
      Reusing it for Postgres/Redis needs the key type generalised. This is the one item
      that changes an EXISTING, tested class rather than adding alongside it.

### T2.B · Implementation, in dependency order

- ✅ **T2.B.1 Settings first** — every new field lands in `settings.py` with a default that
      preserves today's behaviour, so nothing changes until a value is set
  - ✅ T2.B.1.1 `llm_enabled: bool = True` — the FLOOR
  - ✅ T2.B.1.2 `daily_spend_limit_usd: float = 0.0` (0 = off) · `spend_soft_alert_ratio = 0.8`
  - ✅ T2.B.1.3 `rate_limit_per_day: int = 0` (0 = off) · `rate_limit_ip_per_min: int = 0`
  - ✅ T2.B.1.4 `trusted_proxy_hops: int = 0` — trust none by default
  - ✅ T2.B.1.5 `retrieval_top_k: int = 20` · `rerank_top_k: int = 8` — today's hardcoded values
  - ✅ T2.B.1.6 `prompt_version` · `corpus_version` · `index_version`, all `"v1"`
  - ✅ T2.B.1.7 `postgres_circuit_*` · `redis_circuit_*` (threshold 3, cooldown 30)
- ✅ **T2.B.2 Kill-switch floor + daily spend breaker** — `control.py`
  - ✅ T2.B.2.1 `planning_enabled()` returns False immediately when `llm_enabled` is False,
        WITHOUT consulting Redis — a floor that a runtime flag cannot lift
  - ✅ T2.B.2.2 `record_spend(usd)` accumulates into a Redis day-keyed counter with a TTL,
        so the key expires on its own and no cleanup job is needed
  - ✅ T2.B.2.3 `spend_state()` returns ok / soft-alert / breached against the daily limit
  - ✅ T2.B.2.4 Breach flips to degraded (refuse new runs), fail-OPEN on a Redis error —
        same posture as the existing switch: an infra blip must not take the product down
- ✅ **T2.B.3 Rate limiting: two windows, two scopes** — `ratelimit.py` + `main.py`
  - ✅ T2.B.3.1 `allow_request` gains a `scope` label so tenant and IP counters cannot collide
  - ✅ T2.B.3.2 `client_ip(request, hops)` — walk `X-Forwarded-For` right-to-left by
        `trusted_proxy_hops`; 0 hops means use the socket peer and IGNORE the header, because
        a trusted header nobody sets is a header anyone can forge
  - ✅ T2.B.3.3 `_enforce_rate_limit` checks tenant/min, tenant/day, ip/min; a 0 limit skips
        that check entirely so the default stays exactly today's behaviour
  - ✅ T2.B.3.4 Emit which scope refused, for the T3 dashboard panel
- ✅ **T2.B.4 Retrieval depth from settings** — `retrieve.py`
  - ✅ T2.B.4.1 Defaults read from settings, keeping 20/8 so behaviour is unchanged
  - ✅ T2.B.4.2 Explicit call-site arguments still win over settings
- ✅ **T2.B.5 Cache version keys** — `cache.py`
  - ✅ T2.B.5.1 `cache_version()` composes prompt+corpus+index into one short prefix
  - ✅ T2.B.5.2 `cache_aside` prefixes every key, so bumping a version orphans the old
        entries and lets their TTL reap them — no FLUSHDB, no collateral damage
- ✅ **T2.B.6 Infra circuit breakers** — generalise `CircuitBreaker`
  - ✅ T2.B.6.1 Key by `str` instead of `Provider`; venue call sites pass `provider.value`
  - ✅ T2.B.6.2 Verify the 21 existing venue/breaker tests still pass UNCHANGED — if they
        need editing, the refactor changed behaviour and is wrong
  - ✅ T2.B.6.3 Postgres breaker: degrade (history off), never fail the request
  - ✅ T2.B.6.4 Redis breaker: fail-OPEN, bypass cache and keep answering
- ✅ **T2.B.7 Tests for every new behaviour** — floor beats Redis, spend breach refuses,
      each rate-limit scope refuses independently, forged XFF ignored at 0 hops, version
      bump changes the key, infra breaker opens and recovers
- ✅ **T2.B.8 `.env` + `.env.example`** — add all 15 keys in the documented section shape
  - ✅ T2.B.8.1 Structural check: zero duplicate keys, zero trailing comments, zero drift
  - ✅ T2.B.8.2 Resolve the `SERVING_CHAIN` disagreement flagged in T1.R5
- ✅ **T2.B.9 Gate** — ruff · mypy --strict · pytest (expect >150, no regressions) · live plan


---

## T2 · RESULT — verified 2026-09-07

✅ **All of bucket B wired.** Gate: ruff clean · mypy --strict clean on 59 files ·
**169 passed** (150 -> +19, zero regressions).

| what | where | state |
|---|---|---|
| `LLM_ENABLED` floor | `control.py` | ✅ **proven live** |
| daily spend breaker | `control.py` | ✅ wired, `0` = off |
| rate limits: 2 windows x 2 scopes | `ratelimit.py`, `main.py` | ✅ wired, `0` = off |
| `TRUSTED_PROXY_HOPS` + `client_ip()` | `ratelimit.py` | ✅ wired, `0` = ignore XFF |
| retrieval depth | `retrieve.py` | ✅ was hardcoded 20/8 |
| cache version keys | `cache.py` | ✅ every key prefixed |
| infra circuit breakers | `circuit.py`, `cache.py` | 🔄 Redis wired; Postgres NOT |
| 15 keys in `.env` + `.env.example` | both | ✅ 107 keys, 0 dup, 0 drift |
| 15 keys into containers | `docker-compose.app.yml` | ✅ api AND worker |

### The live proof
- ✅ **T2.R1 The floor beats the runtime flag.** With Redis holding
      `planning:enabled = 1` (ENABLED) and `LLM_ENABLED=false`, `POST /plan` returned
      **HTTP 503**. A static operator decision outranks a flag someone set and forgot,
      which is the entire reason the floor exists.
- ✅ **T2.R2 Nothing changed by default.** A plan before and after: `venues: ['groq']`,
      $0.000235, 5 items, HTTP 202. Every new limit ships at `0`/off.
- ✅ **T2.R3 Settings reach the containers** — verified INSIDE api and worker, not just
      in `settings.py`. This is the failure that hid the whole local-inference feature
      for a session; it is now checked rather than assumed.

### Defects this task surfaced
- ⚠️ **T2.D1 `control.py` importing `get_settings()` broke the kill switch.**
      `get_settings()` validates the WHOLE config, so a missing `OPENAI_API_KEY` would
      have taken the cost control down — failing in exactly the situation you reach for
      it. Caught by two EXISTING tests. Fixed the code, not the tests: control.py now
      reads the environment directly, the pattern settings.py already reserves for the
      dispatch path.
- ⚠️ **T2.D2 A duplicate `SERVING_CHAIN` was sitting in `.env`** — a stray block at the
      top of the file with a TRAILING COMMENT
      (`SERVING_CHAIN=local-sglang,groq,openai    # SGLang (current)`), pasted from
      switch-engine instructions I gave earlier. Inert only because the documented
      assignment came later and won. Removed; this is the second duplicate-key landmine
      in this file, which is why the check is now structural.
- ⚠️ **T2.D3 The new process-wide breaker registry leaked between tests.** A suite that
      provokes a Redis failure left the breaker OPEN, so `test_cache` recomputed instead
      of hitting cache — it passed alone and failed in the suite. Correct in production,
      wrong to inherit in a test: added `reset_infra_breakers()` and wired it into
      conftest beside the existing settings-cache reset. The test's assertion was right
      and was NOT weakened.

### Still open
- 🔄 **T2.O1 The Postgres breaker is settings-only.** `runs.py` has no degrade path, so
      wiring one would turn a persistence failure into silent history loss — a design
      change beyond this task. Documented in `.env` rather than left as a silent gap.
- ⏳ **T2.O2 `SERVING_CHAIN` still disagrees with the Makefile.** `.env` says
      `local-sglang,groq,openai`; the Makefile chains stop at `groq`. `.env` governs the
      no-make path, so today the bare-compose path HAS a paid last-resort leg and
      `make up` does not. Left for you: removing a paid fallback reduces availability,
      and that is a policy call, not a tidy-up.


---

## T3 · RESULT — verified 2026-09-07

✅ **Done.** Gate: ruff clean · mypy --strict clean on 59 files · **169 passed**.

### T3.1 · Instrumentation added FIRST (6 new series, 16 total)

| metric | labels | answers |
|---|---|---|
| `tp_stage_duration_seconds` | `stage` | where the time goes: geocode / gather / compose / critic |
| `tp_venue_latency_seconds` | `provider` | is local actually slower than Groq |
| `tp_cache_events_total` | `tool`, `result` | hit / miss / skipped / error |
| `tp_itinerary_outcome_total` | `kind` | grounded vs degraded vs not_found |
| `tp_errors_total` | `type` | transient vs timeout vs our-bad-request |
| `tp_retrieval_results` | — | how much grounding material each query got |

- ✅ T3.1.a Stage timing recorded in a `finally`, so a stage that RAISES still reports how
      long it burned. Timing only the happy path makes a slow failure look instantaneous.
- ✅ T3.1.b Error labels are CLASSES, never messages — a message label is unbounded
      cardinality and will eventually take Prometheus down.
- ✅ T3.1.c Cache label is the tool prefix, not the full key, for the same reason.

### T3.2 · Dashboard rebuilt — 37 panels, 5 question-titled sections
`0 — Is the service healthy right now?` · `1 — Which venue is actually answering, and what
does it cost?` · `2 — Is the product refusing what it must?` · `3 — Where does the time
actually go?` · `4 — Are the parts underneath still healthy?`

- ✅ T3.2.a **All 37 panels carry a `description`** — asserted at build time, not by eye
- ✅ T3.2.b All 16 per-venue panels read **"not served since restart"**, verified in the
      written JSON. That is INFORMATION: it means the chain never reached that leg, which
      is exactly what you want to see on the paid ones.

### T3.3 · No dead panels — the rule that shaped the whole task
- ✅ T3.3.a Build-time assertion: every `tp_*` referenced by a panel must exist in the
      emitted set, or the generator refuses to write the file
- ✅ T3.3.b **40/40 panel queries executed against live Prometheus: ZERO errors**
- ✅ T3.3.c 27 returned data; the 13 empty ones are precisely `local-sglang` (engine down),
      `local-vllm` (never run) and `openai` (never reached) — each showing its
      "not served since restart" text rather than a bare `No data`

### T3.4 · Verified by LOADING it, not by validating JSON
- ✅ Grafana 13.2.0 reports it back: 5 sections, 37 panels, title `Voyantra — service overview`

### Defects and corrections
- ⚠️ **T3.D1 My metric probe was wrong, not the code.** `grep`-ing worker `/metrics` via
      `curl` returned 0 samples for all six new series — because `curl` is not installed in
      that image. Reading the endpoint with Python showed every series present. Fifth time
      this session the measuring instrument was the broken part.
- 📝 **T3.D2 Correction to an earlier claim.** I said the critic "is not in the eval path
      at all". True of the EVAL harness, which calls `compose_node` directly — but
      `tp_stage_duration_seconds{stage="critic"}` records real traffic, so the critic DOES
      run in production. The earlier statement was too broad.
- ⚠️ **T3.D3 A mislabelled panel.** "Failure rate" showed `idle` when empty, but empty there
      means NO FAILURES. A panel that mislabels good news is as bad as one that hides bad
      news; changed to `0 — no failed runs`.
- ⏳ **T3.O1 A stray dashboard exists** — `uid=dfxi63ldmhla8b`, title "Voyantra", no folder.
      Not created by this provisioning path. Left alone rather than deleted unasked.


---

# PHASE 10 — Clearing the backlog, ordered by BLAST RADIUS
*(planned 2026-09-07; work the list top-down, gate green between each)*

Ordering rule: **what can this break if I am wrong?** Measurement cannot break anything.
Config that only touches the engine tier cannot break the app. Code that changes a failure
path can. Decisions that trade away availability are not mine to make at all.

## TIER 0 — NO RISK · read-only or measurement, nothing changes

- ✅ **R0.1 `make which-engine`** — the one target never actually executed. Read-only.
- ✅ **R0.2 `make bench-groq`** — 404'd on the retired model and was never re-run after the
      Groq rung was repaired, so the local-vs-hosted comparison has a hole in it. Costs a
      fraction of a cent; changes nothing.
- ✅ **R0.3 Verify the Groq price** — `(0.29, 0.59)` for `qwen/qwen3.8-27b` is an ESTIMATE
      I invented. A wrong price silently corrupts cost accounting AND the budget gate, and
      both fail quietly. Look it up; correct the table only if it differs.
- ✅ **R0.4 Identify the stray dashboard** — `uid=dfxi63ldmhla8b`, no folder. Inspect only;
      deleting is TIER 1.

## TIER 1 — VERY LOW RISK · config, reversible, app behaviour unchanged

- ✅ **R1.1 `start_period` covers a cold LOAD, not a cold DOWNLOAD** — 900 s was enough for
      weights already on disk (360 s observed) but not for fetching 5.5 GB. `make sglang-up`
      would call a live download dead. Touches only the gpu tier.
- ✅ **R1.2 kind image drift** — `.env` pins `v1.31.2`, the cluster runs `v1.31.6`. Reconcile
      so the pin describes reality; a pin that lies is worse than no pin.
- ✅ **R1.3 MOOT** — R0.4 proved there is no stray dashboard to remove.

## TIER 2 — LOW RISK · additive code, covered by tests

- ✅ **R2.1 Embedder-mismatch guard** — index and query embedder must match or RAG degrades
      **silently**. Today nothing checks. Detect and WARN loudly; do not fail startup, because
      a hard failure here would take down a working app to report a config smell.
- ✅ **R2.2 Postgres breaker wiring** — settings and breaker exist, `runs.py` has no degrade
      path. Needs care: done naively this converts a persistence failure into SILENT history
      loss, which is worse than the error it replaces.

## TIER 3 — YOURS TO DECIDE · not mine to choose

- ✅ **R3.1 `SERVING_CHAIN` policy** — `.env` keeps `openai` last, the Makefile chains stop at
      `groq`. Removing a paid last-resort leg trades cost for availability.
- ✅ **R3.2 Confirm `qwen/qwen3.8-27b` as the D4 Groq model** — I picked it because it was the
      only one of four that returns usable content, but ratifying it is a quality/cost call.
- ✅ **R3.3 Eval gate n=7 fragility** — widen the golden set, or state "zero hallucinations"
      as the deliberate bar. Right now that bar exists by ARITHMETIC ACCIDENT.
- ✅ **R3.4 Git staging** — commands prepared, never run, per the standing constraint.

## TIER 4 — HIGHER RISK / LARGER · deliberately last

- ✅ **R4.1 First vLLM run** — wired, never executed. Contends for the same GPU as SGLang.
- 🔄 **R4.2 GPU node group + scale-to-zero (Terraform)** — WRITTEN + VALIDATED, never planned.
- ⏸️ **R4.3 VHDX compact** — deferred by choice; builder prune done instead.


---

## TIER 0 · RESULT — 2026-09-07 · all four done, nothing broken

- ✅ **R0.1 `make which-engine` ran** — correctly reports `vllm down` / `sglang down` and
      prints the chain. The one target that had never been executed now has been.
- ⚠️ **R0.2 uncovered a leftover before it could run.** `make bench-groq` still defaulted to
      `llama-3.3-70b-versatile` — I repaired `models.py` when the Groq rung died but never
      the bench target or `bench_venue.py`'s docstring. Fixed both, then benchmarked.

  **The comparison that was missing:**

  | | local-sglang (7B AWQ, RTX 3060) | groq (qwen3.8-27b) |
  |---|---|---|
  | TTFT p50 | **50 ms** | 351 ms |
  | TTFT p95 | **559 ms** | 892 ms |
  | TPOT p50 | 15.2 ms | **2.0 ms** |
  | tok/s | 60.8 | **187.4** |

  - ✅ R0.2.1 They SPLIT the metrics, exactly as the harness docstring predicted. Local wins
        first-token by 7x (no network hop); Groq wins throughput by 3x.
  - ✅ R0.2.2 Crossover computed: `50 + 15.2n` vs `351 + 2.0n` -> **n ~= 23 output tokens**.
        Below that local feels faster; above it Groq finishes sooner. A ~400-token intro sits
        far past the crossover, which is exactly why the 5-city trip was 16.0s local vs 10.9s
        hosted. The earlier wall-clock result was not noise; it was predictable from these two
        numbers, and now it is.
- ⚠️ **R0.3 My Groq price was wrong, in the dangerous direction.**
      Verified against `console.groq.com/docs/models.md` AND the model page: **$0.80 in /
      $4.00 out** per 1M tokens. My estimate `(0.29, 0.59)` was out **2.8x on input and 6.8x
      on OUTPUT** — and output is where itinerary spend lands.
  - ✅ R0.3.1 Measured impact: a 2-call plan reported **$0.000228**, truth **$0.000960** —
        **4.2x under-reported**. The `$0.30` per-itinerary cap was really admitting **~$1.27**.
  - ✅ R0.3.2 `cost_usd()` feeds BOTH the runtime cap and the eval budget gate, so both were
        quietly weaker than they claimed. This is the exact hazard the file's own comment
        warned about for UNPRICED models — I introduced the same failure with a wrong price.
  - ✅ R0.3.3 Also recorded: `openai/gpt-oss-20b` is 10x cheaper ($0.075/$0.30) and STILL
        unusable — it returns empty `message.content`. Cheap is not a price if it cannot answer.
- 📝 **R0.4 The "stray dashboard" was my error, not a defect.** `dfxi63ldmhla8b` is
      `type: dash-folder` — the **Voyantra folder** that `grafana-dashboards.yml` provisions.
      My earlier `/api/search` read did not distinguish `dash-folder` from `dash-db`. Sixth
      time this session the instrument was the broken part, and the only one that invented a
      defect rather than hiding one.

**Gate after Tier 0:** ruff clean · 169 passed · app serving.


---

## TIER 1 · RESULT — 2026-09-07

- ✅ **R1.1 The download no longer happens inside the healthcheck window.**
  - ✅ R1.1.1 Root cause restated: `start_period` was covering TWO durations at once —
        a cold LOAD (~360 s measured) and a cold DOWNLOAD (~25 min measured). Sized for
        the load it kills live downloads; sized for the download it waits 40 minutes on a
        wedged engine. Neither is a timeout worth having.
  - ✅ R1.1.2 `sglang-up` and `vllm-up` now run `ensure_weights.sh` BEFORE `up --wait`,
        so by the time the healthcheck starts there is only ever a load to wait for.
        Verified in both dry-runs: preflight -> pull -> **weights** -> wait.
  - ✅ R1.1.3 `ENGINE_WAIT=900` is now an HONEST budget against a 435 s worst observed
        load, rather than an optimistic one against a download it could never cover.
        Escape hatch: `SKIP_WEIGHTS=1`.
  - ⚠️ R1.1.4 **My fix was itself a regression, caught by measuring it.** The first version
        added **2m6s to every bring-up**: the script slept a full 120 s sampling window
        before noticing a warm-cache download had already finished in seconds.
    - ✅ R1.1.4a FAST PATH: if a `*.safetensors` exists in the snapshot AND no
          `*.incomplete` exists anywhere, exit immediately without starting a container.
          **2m6s -> 1.0s.**
    - ✅ R1.1.4b Liveness now polled every 5 s while the cache is still only MEASURED on
          the 120 s cadence — `cache_bytes` spawns a container, so sampling it frequently
          would cost more than the download.
    - ✅ R1.1.4c The fast path was tested for FALSE POSITIVES, which is the direction that
          matters: an always-true check would silently skip real downloads.
          complete cache -> pass · empty volume -> fail · safetensors + a lurking
          `.incomplete` -> fail. All three correct.
  - ✅ R1.1.5 The compose comment claiming the window covers "a cold weight load" now says
        what it actually covers, and warns that a hand-started container with a cold cache
        WILL expire at 900 s.
- 📝 **R1.2 There is no kind image drift. The claim was mine and it was wrong.**
  - ✅ R1.2.1 Measured: node image `kindest/node:v1.31.2`, all four kubelets `v1.31.2`,
        server `gitVersion v1.31.2`. `.env` pins `v1.31.2`. They AGREE.
  - ✅ R1.2.2 `v1.31.6` appears nowhere in the repository.
  - 📝 R1.2.3 The claim came from a prior-session summary and I repeated it across many
        turns without once checking it. Seventh instrument error of the session and the
        second INVENTED defect — but the first I propagated rather than generated, which
        is the worse kind: a fabricated fact with a long half-life.
- ✅ **R1.3 MOOT** — R0.4 proved the "stray dashboard" is the provisioned Voyantra folder.

**Gate after Tier 1:** ruff clean · mypy clean on 59 files · 169 passed.


---

## TIER 2 · RESULT — 2026-09-07

**Gate:** ruff clean · mypy clean on 59 files · **177 passed** (169 -> +8).

### ✅ R2.1 · Embedder-mismatch guard
- ✅ R2.1.1 **A dimension check would catch NOTHING.** `text-embedding-3-large` reduced to
      1024 and `voyage-3` both emit 1024-d vectors, so swapping providers passes every
      structural check Qdrant can make while the query vector lands in a different space.
      Cosine still ranks, still returns, just quietly worse. Only recording WHICH MODEL
      built the index can catch it.
- ✅ R2.1.2 Provenance stamped as a sentinel point INSIDE the collection, not a sidecar
      file — restore the volume and the fact comes back with it.
- ✅ R2.1.3 `ingest.py` stamps at seed time; `get_retriever()` compares at construction.
- ✅ R2.1.4 **Loud, never fatal** — warning log naming BOTH models plus
      `tp_errors{type="embedder_mismatch"}`, already charted by the dashboard's
      "Errors by type" panel. Raising would take a working app down over a quality smell.
- ✅ R2.1.5 A MISSING stamp is not a mismatch. Pre-existing indexes have none, and a guard
      that fires on every one of them is a guard people learn to ignore.
- ✅ R2.1.6 6 tests, incl. the two failure directions: mismatch fires, absence stays silent.
- ✅ R2.1.7 **Verified against the LIVE index.** Unstamped -> silent (no false alarm).
      Stamped `text-embedding-3-large`. Simulated `voyage-3` query -> metric + warning
      naming both models.
  - 📝 R2.1.7a The stamp ASSERTS the current embedder built the existing index rather
        than proving it; the alternative was a full re-embed. A future `make seed` writes
        a stamp that is proven.

### ✅ R2.2 · Postgres breaker wired at `session_scope()`
- ✅ R2.2.1 Single chokepoint: every persistence call funnels through it, and `NullPool`
      means a fresh connection per call — so a dead Postgres costs every request a full
      connect timeout. The breaker makes that one probe per cooldown.
- ✅ R2.2.2 **It RAISES; it does not degrade.** "Degrading gracefully" here would mean
      returning without persisting: `create_run` would hand back a run id that does not
      exist and `mark_succeeded` would drop a finished itinerary, neither distinguishable
      from success by the caller. Silent history loss is worse than the error it replaces.
- ✅ R2.2.3 Cost stated honestly: a brief outage can be extended by up to one cooldown.
      Three CONSECUTIVE failures are needed to open, so a single blip does not.
- ✅ R2.2.4 2 tests: open -> raises; closed -> complete no-op.
  - ⚠️ R2.2.4a My first test constructed an IMPOSSIBLE state — it injected `now=0.0` into
        `record_failure` while `session_scope` reads the real monotonic clock, so the
        cooldown looked long expired and a probe was admitted. Same injected-vs-real clock
        trap that produced the earlier `snapshot()` reporting bug. Test fixed, not the code.
- ✅ R2.2.5 **Live:** a real plan succeeded, no `postgres_*` error series — the breaker
      never tripped, which is the correct result for a healthy database.

### Incidental confirmation
- ✅ The same Kyoto plan now reports **$0.000816**, up from **$0.000223** before R0.3.
      That ~3.7x jump is the corrected Groq price landing in real cost accounting — the
      earlier figure was the under-report, not a cheaper run.


---

## TIER 3 · RESULT — 2026-09-07 · decided and executed

**Gate:** ruff clean · mypy clean on 59 files · **177 passed**.

### 📝 R3.1 · Chain — DECIDED TWICE, because my first analysis was wrong
- ⚠️ R3.1.1 I recommended `local -> openai -> groq` on the claim that groq is **6x the
      cost of gpt-4o-mini**. You reasonably acted on it. **The comparison was invalid.**
- ✅ R3.1.2 `gpt-4o-mini` is the **CHEAP** tier model and the planner NEVER composes
      there — it composes on MID and criticises on FRONTIER, where OpenAI serves `gpt-4o`:

  | tier | used by | openai | groq |
  |---|---|---|---|
  | CHEAP | eval judge only | gpt-4o-mini $0.15/$0.60 | qwen3.8-27b $0.80/$4.00 |
  | **MID** | **compose_node** | **gpt-4o $2.50/$10.00** | **qwen3.8-27b $0.80/$4.00** |
  | **FRONTIER** | **critic** | **gpt-4o $2.50/$10.00** | **qwen3.8-27b $0.80/$4.00** |

- ✅ R3.1.3 On the path the app actually uses, **groq is 2.8x CHEAPER**. Measured on the
      identical plan: **groq-first $0.000811 · openai-first $0.002659** — 3.3x worse.
- ✅ R3.1.4 Reverted to `local-sglang,groq,openai` and verified live: `venues: ['groq']`
      at $0.000811.
- ✅ R3.1.5 `.env` and the Makefile now AGREE for the first time (closes T2.O2), and all
      four ENGINE values were re-checked.
- ✅ R3.1.6 The rationale comment now states the comparison must be made WITHIN a tier,
      and records the trap explicitly — both numbers were real, the comparison was not.
- ✅ R3.1.7 **R3.2 folded in**: `qwen/qwen3.8-27b` is ratified by elimination — it is the
      only one of Groq's four served models that returns usable content.

### ✅ R3.3 · Eval gate widened — and a side effect caught before it shipped
- ✅ R3.3.1 Golden set **7 -> 20 cases**. At n=7 faithfulness could only be k/7, so 0.95
      meant 7/7 or fail. At n=20, **19/20 = 0.95 exactly**: "at most one failure", a bar
      someone could have chosen.
- ✅ R3.3.2 Chosen for coverage, not padding: 5 multi-day, 3 multi-interest, 1 thin
      (single POI), 3 empty-POI, an interest/POI mismatch, a non-Latin city name, and an
      injection-shaped city name.
- ✅ R3.3.3 Three adversarial cases behaved correctly on the first run:
      `injection-shaped-city` degraded honestly (treated as an unfindable PLACE, not an
      instruction) · `interest-mismatch` used what existed and invented nothing ·
      `unicode-city` survived prompt construction and the JSON round-trip.
- ⚠️ R3.3.4 **Widening WEAKENED the retrieval gate, and I nearly shipped it.** The corpus
      holds 5 cities; I added 12 it has never ingested. `grounded_rate` collapsed
      **0.857 -> 0.30**, dropping the gate floor to **0.25** — adding tests made the gate
      worse, which is the exact opposite of the intent.
  - ✅ R3.3.4a Root cause: on `--retrieve`, an uningested city measures CORPUS COVERAGE,
        not retrieval quality. The two were being averaged into one number.
  - ✅ R3.3.4b Fixed with `corpus_backed` on each case; `--retrieve` scores only those.
        RAG baseline restored: 6 cases, grounded **1.0**, faithfulness 1.0, relevance
        0.967 — floor back to **0.95**.
- 🔄 R3.3.5 **The RAG gate still has the granularity problem**, now honestly located: it
      is limited to 6 cases because the CORPUS only covers 5 cities, not because of the
      threshold. Growing it needs real POI data for real cities — inventing that data to
      pad a grounding corpus would be self-defeating. The FIXTURE gate, where faithfulness
      is actually measured, has the n=20 fix.


---

## TIER 4 · R4.1 RESULT — vLLM's first ever run, 2026-09-07

- ⚠️ **R4.1.1 It crash-looped, and the error named nothing useful.**
      `RuntimeError: UVA is not available`, restarting every ~32 s. No mention of WSL, no
      mention of a flag, and it looks like a memory problem — which is what I assumed.
- 📝 **R4.1.2 My first hypothesis was wrong.** I assumed WSL2 lacks UVA. Measured
      directly: `cudaDevAttrUnifiedAddressing = 1`, pinned allocation OK. The GPU
      supports it fine.
- ✅ **R4.1.3 Real root cause, read from vLLM's own source:**
      `is_uva_available()` is just `is_pin_memory_available()`, and
      `platforms/cuda.py::is_pin_memory_available` gates on WSL. This host runs kernel
      **5.15.167.4**, well past the 4.19.121 minimum — so the version gate passes and then:

          # On compatible WSL2 kernels, pinned memory is supported but
          # disabled by default. Enable it via VLLM_WSL2_ENABLE_PIN_MEMORY=1.
          return envs.VLLM_WSL2_ENABLE_PIN_MEMORY

      **Pinned memory is off by default on WSL2.** One environment variable.
- ✅ **R4.1.4 Fixed** — `VLLM_WSL2_ENABLE_PIN_MEMORY: "1"` in `docker-compose.gpu.yml`,
      with the whole diagnosis in a comment so nobody repeats the 10-minute hunt.
- ✅ **R4.1.5 HEALTHY in 195 s** — model 5.29 GiB, KV cache 56,240 tokens, zero UVA errors.
- ✅ **R4.1.6 It GENERATES** — three correct Kyoto suggestions, `finish_reason: stop`.
- ✅ **R4.1.7 End-to-end through the app** — `venues: ['local-vllm']`, **$0.00**, 5 items.

### ⚠️ R4.1.8 vLLM BEATS SGLang on every measured axis

| | local-vllm | local-sglang | groq |
|---|---|---|---|
| TTFT p50 | **33 ms** | 50 ms | 351 ms |
| TTFT **p95** | **45 ms** | **559 ms** | 892 ms |
| TPOT p50 | **14.8 ms** | 15.2 ms | 2.0 ms |
| tok/s | **66.5** | 60.8 | 187.4 |
| time to healthy | **195 s** | 360-435 s | - |

- ✅ R4.1.8a The tail is the striking one: **45 ms vs 559 ms p95**, 12x better. SGLang pays
      a large first-request spike after idle; vLLM does not.
- ⚠️ R4.1.8b **But vLLM leaves almost no headroom**: 442 MiB free versus SGLang's 1708 MiB.
      On a desktop GPU that is the difference between "fine" and "dies when you open
      another browser tab" — exactly the late OOM `docs/gpu-venue.md` warns about.
- ⏳ R4.1.8c **The default engine is still SGLang and I have NOT changed it.** vLLM is
      faster on every metric and riskier on the one that is not a metric. That trade is
      a decision, not a benchmark result.


---

## TIER 4 · RESULT — 2026-09-07

### ✅ R4.3-alt · Disk: builder prune only, by your choice
- ✅ R4.3.1 **19.48 GB reclaimed.** Build cache 32.5 GB -> 13.02 GB; reclaimable
      19.55 GB -> 78 MB.
- ✅ R4.3.2 Verified it touched NOTHING else: volumes still **616**, both engine images
      intact (`lmsysorg/sglang` 52.2 GB, `vllm/vllm-openai` 30.8 GB), 27 containers still
      running, `/health` still ok.
- ⚠️ R4.3.3 **Two of the three obvious moves would have been destructive**, and the trap
      was the same one as before:
      - `docker image prune -a` claims **105 GB** — and would delete both engine images,
        because with the engines stopped they report `containers=[NONE]`. "Not currently
        running" is not "not needed". That is 83 GB of re-download.
      - `docker volume prune` claims 20.64 GB — **593 of 616 volumes read as dangling**,
        including the 2-4 h OSM import and another project's data. Never.
- ⏸️ R4.3.4 **VHDX compact deferred.** `docker_data.vhdx` is **367 GB** on disk against
      ~253 GB of real content — roughly **114 GB of slack** — and C: has 48.3 GB free.
      It needs Docker fully stopped, which also kills the tooling doing the stopping, so
      it is a walk-through rather than something to run from here.

### 🔄 R4.2 · GPU node group — written, validated, NOT planned
- ✅ R4.2.1 `infra/terraform/gpu.tf`: scale-to-zero GPU node group, `gpu_enabled=false`
      by default so applying it costs nothing until deliberately switched on.
- ✅ R4.2.2 `terraform fmt` applied · `terraform validate` -> **"Success! The
      configuration is valid."**
- ⏳ R4.2.3 **NEVER PLANNED — this is the honest status.** validate proves syntax and
      provider schema, nothing else. Unverified against reality: regional availability of
      `g5.xlarge`, G-instance quota (zero on new accounts by default), and the AMI/taint
      interaction. Same category `bench_venue.py` occupied before it ran.
- ⏳ R4.2.4 **Deliberately NOT merged into `module.eks`.** The merge is one line, but it
      edits a resource already in state and I cannot read a plan to see whether that
      updates or REPLACES the cluster. Left for someone who can.
- ⏳ R4.2.5 The Helm chart has no matching toleration/nodeSelector, so a GPU node would
      currently be dead capacity even if created.
- ✅ R4.2.6 Design decisions recorded in-file: `min_size=0` because a g5.xlarge left
      running is ~$730/month and idle GPU destroys the self-hosting argument faster than
      any token bill · `disk_size=200` because the engine images are 31-52 GB and a
      default 20 GB root disk fails as a *stuck node*, not a full disk · a taint so the
      API and Postgres cannot land on the most expensive machine in the cluster.

### 📌 WHEN CREDENTIALS EXIST — resume here
1. `cd infra/terraform && terraform init && terraform plan -var gpu_enabled=true`
2. Confirm `g5.xlarge` is available in `var.region` and that G-instance quota > 0.
3. Read the plan for whether merging changes or REPLACES the existing node group.
4. Merge `local.gpu_node_group` into `eks.tf`'s `eks_managed_node_groups`.
5. Add toleration + nodeSelector to the Helm chart, or the node stays empty.
6. Only then is R4.2 done.


---

# PHASE 11 — Brutal inspection: 2 documents + 2 single-command scripts
*(planned 2026-09-07, survey first, nothing written yet)*

## S · SURVEY RESULT — what the app actually is

- ✅ **S1 CONFIRMED ASYNCHRONOUS.** `POST /plan` and `/trip` return **202 + run_id** and
      `celery_app.send_task(...)`. The work runs in the WORKER. Any document that describes
      a synchronous pipeline would be describing a different application.
- ✅ **S2 TWO metrics endpoints, two scrape jobs** — `tp-api` (`api:8000/metrics`) and
      `tp-worker` (`worker:3005/metrics`). Most pipeline metrics live on the WORKER.
- ✅ **S3 TWO Jaeger services** — `init_tracing("tp-api")` and `init_tracing("tp-worker")`.
      A plan therefore produces **two separate traces**, not one. The document must say how
      to correlate them, because looking only at `tp-api` shows a 202 and nothing else.
- ✅ **S4 Langfuse is fed by an OTel exporter on the SAME TracerProvider**
      (`tracing.py::_add_langfuse_exporter`), not a separate SDK. It sees the same spans.
      This is materially different from the reference project and changes what to expect.
- ✅ **S5 16 metrics, exact labels confirmed from source:**
      `tp_runs{status}` · `tp_run_duration_seconds` · `tp_run_cost_usd` ·
      `tp_llm_calls{tier,provider}` · `tp_critic_revisions` · `tp_dispatch{endpoint,outcome}` ·
      `tp_rate_limit_events{scope,outcome}` · `tp_llm_tokens{provider,direction}` ·
      `tp_llm_cost_usd{provider}` · `tp_venue_circuit_state{provider}` ·
      `tp_stage_duration_seconds{stage}` · `tp_venue_latency_seconds{provider}` ·
      `tp_cache_events{tool,result}` · `tp_itinerary_outcome{kind}` · `tp_errors{type}` ·
      `tp_retrieval_results`
- ✅ **S6 7 spans:** `agent.plan` · `trip.plan` · `agent.geocode` · `agent.gather` ·
      `agent.compose` · `agent.critic` · `llm.complete`
- ✅ **S7 Cache keys are version-prefixed** — `f"{cache_version()}:{key}"` where the version
      is `PROMPT_VERSION.CORPUS_VERSION.INDEX_VERSION`. Four caches: `geo`, `pois:`, `wx:`,
      `route:`. A guessed `redis-cli del` cannot work.
- ✅ **S8 Corpus is 26 points across 5 cities**, and `indexed_vectors_count = 0` — below the
      10000 HNSW threshold, so search is brute-force. Correct at this size, but it means
      retrieval latency here says nothing about retrieval latency at scale.
- ✅ **S9 37 panels in 5 sections** · **108 runs in Postgres, 107 succeeded**
- ⚠️ **S10 DEFECT FOUND, AND IT IS MINE: the spend breaker cannot fire.**
      `record_spend()` is **never called from anywhere**. `spend_today()` reads a Redis key
      nothing ever writes, so it always returns 0.0 and `DAILY_SPEND_LIMIT_USD` can never
      trip. My T2 tests passed because they monkeypatched `spend_today`.
      This is the exact "declared vs working" failure this project keeps finding, and I
      created it while adding the control that was supposed to prevent it.
      **It must be fixed BEFORE the document is written**, or the document would certify a
      dead cost control as working — which is worse than not having one.

## A · FIX FIRST (documentation must not certify a lie)
- ✅ **A1 Wire `record_spend()`** at the point where cost is known — beside
      `record_venue_usage(...)` in `gateway.py`, which already receives `cost_usd`.
- ✅ **A2 Test that proves it end-to-end**, NOT by mocking `spend_today` — a real write then
      a real read, so the same bug cannot recur.
- ✅ **A3 Gate green afterwards**: ruff · mypy --strict · pytest.

## B · `docs/INSPECTION.md` — the working battery
- ✅ **B1 Instrument primer** — four tools, four different questions, ports, and the three
      readings that mislead (empty ≠ zero · $0.00 is CORRECT locally · an absent span is
      evidence).
- ✅ **B2 ~18 queries, each naming which component it exercises**, with the expected
      desired-state response and how to tell a pass from a plausible-looking failure.
- ✅ **B3 Every query annotated per instrument** — Prometheus series, Grafana panels,
      Jaeger shape, Langfuse record.
- ✅ **B4 The corpus caveat stated up front** — 5 cities only. Each query labelled as
      testing RETRIEVAL QUALITY or CORPUS COVERAGE, never conflating them.

## C · `docs/INSPECTION_DEEP.md` — the full manual
- ✅ **C1 Part 0** — the four instruments and how they do not overlap.
- ✅ **C2 Part 1: Prometheus, all 16 metrics** — for each: what it IS, what it TELLS you,
      WHY it exists (the failure it makes visible), exact PromQL, what a bad value means,
      which endpoint it lives on, and its gotchas.
- ✅ **C3 Part 2: Grafana, all 37 panels** across the 5 sections, panel by panel.
- ✅ **C4 Part 3: Jaeger from ZERO** — what a span and a trace are · how to read the
      waterfall (horizontal = time, vertical = NESTING not time) · why children do not sum
      to the parent · every span in this app · **the trace SHAPES** · absent spans as
      evidence · **why a plan produces TWO traces** and how to correlate them.
- ✅ **C5 Part 4: Langfuse** — trace vs observation, every field, and the retrieval-vs-model
      fault-attribution workflow.
- ✅ **C6 Part 5** — the battery again, query by query, instrument by instrument.
- ✅ **C7 Part 6** — the failover drill, both engines.

## D · The two scripts
- ✅ **D1 `scripts/_inspect_common.py`** — ALL shared logic, parameterised by engine. Two
      near-identical files would drift the first time either was touched.
- ✅ **D2 `scripts/inspect_stack_sglang.py`** · **D3 `scripts/inspect_stack_vllm.py`** —
      thin entrypoints.
- ✅ **D4 Fault injection by DNS blackhole**, never by config removal: removing a leg from
      the chain makes it ABSENT, which tests configuration, not resilience.
- ✅ **D5 VERIFY EVERY INJECTION LANDED** and abort with "this step proves nothing" if not.
      Includes a connection-pool drain, because a pooled socket rides straight past
      `/etc/hosts` and turns a green result into a lie.
- ✅ **D6 Clear the cache between steps** — otherwise the second question is served from
      Redis without touching any venue.
- ✅ **D7 Full ladder**: engine → groq → openai → clean failure. Never a fabricated itinerary.
- ✅ **D8 Everything else in one run** — containers · Postgres · Qdrant non-empty · Redis ·
      Celery · Prometheus targets · every metric present · every dashboard query executes ·
      Jaeger receiving · Langfuse recording · kill switch · spend breaker · 3 rate-limit
      scopes · venue breaker opens AND recovers · infra breakers · embedder stamp · cost
      zero-local/non-zero-hosted · `.env` drift, duplicates, trailing comments · `.env` ↔
      Makefile chain agreement.
- ✅ **D9 Restore all state**, always, including on failure.

## E · Cache clearing
- ✅ **E1 `make cache-clear` / `make cache-ls`** built on the REAL key shape
      (`{PROMPT_VERSION}.{CORPUS_VERSION}.{INDEX_VERSION}:{tool}:...`).
- ✅ **E2 Also document** clearing run history in Postgres, and state honestly that
      Prometheus counters CANNOT be reset without restarting the process.
- ✅ **E3 The caching feature is NOT removed** — only the commands to clear it.

## Quality bar for every claim
- ⏳ No `✅` without a command whose output is quoted. Unverified stays `⏳`.
- ⏳ Every metric and panel cross-checked against `metrics.py` and the dashboard JSON before
      it appears in prose.


---

## PHASE 11 · A · RESULT — the spend breaker is now alive, 2026-09-07

**Gate:** ruff clean · mypy --strict clean on 59 files · **184 passed** (177 -> +7).

- ⚠️ **A.0 The bug, restated plainly.** `record_spend()` existed, `spend_today()` read the
      key it writes, `spend_state()` compared that to the limit, and `planning_enabled()`
      consulted it — every piece correct, the whole inert, because **nothing ever called
      `record_spend()`**. `DAILY_SPEND_LIMIT_USD` could not trip at any value.
  - 📝 A.0.1 My T2 tests passed because they **monkeypatched `spend_today`**. That tests the
        arithmetic BELOW the bug and can never see it. A control exercised only through a
        mock of its own input is a control nobody has tested.
- ✅ **A1 Wired at the point cost is known** — beside `record_venue_usage()` in
      `gateway.py`, which already receives `resp.usage.cost_usd`.
  - ✅ A1.2 Recorded even at `0.0`, so a self-hosted day reads ZERO rather than absent.
  - ✅ A1.3 **Breaker-guarded.** `record_spend` now runs on EVERY LLM call; unguarded, a
        dead Redis would add its 0.25 s connect timeout to every one of them. Reuses
        `infra_breaker("redis")` — one Redis, one piece of state about whether it is up.
- ✅ **A2 Tested without mocking the thing under test** — `test_spend_breaker.py`, 7 tests.
  - ✅ A2.1 **Falsification check: the tests were PROVEN to catch the bug.** Reverting the
        one-line fix made `test_gateway_records_spend_for_the_venue_that_served` and
        `test_gateway_records_zero_cost_calls_too` FAIL; restoring it made all 7 pass.
        A regression test nobody has seen fail is a regression test nobody has tested.
  - ✅ A2.2 Round-trip through a real store: `record_spend` WRITES, `spend_today` READS,
        nothing patched between them.
  - ✅ A2.3 Accumulation across calls, TTL present, `$0` recorded not skipped, and a dead
        Redis never failing the request that triggered it.
  - ⚠️ A2.4 Writing the tests exposed a contract detail: a LOCAL venue has no catalog
        entry, so `model_for()` returns None and the gateway **skips the leg** unless the
        adapter itself reports a loaded `.model`. My first fake omitted it and produced an
        empty chain rather than a free call.
- ✅ **A3 Verified LIVE, not just in tests:**

  | | spend key |
  |---|---|
  | before any run | *(absent)* |
  | after a `local-sglang` run at $0.00 | `0` |
  | after `groq` run 1 at $0.00092 | `0.00092` |
  | after `groq` run 2 at $0.000924 | `0.001844` |

  - ✅ A3.1 The absent -> `0` transition is the property working: **absent and zero are now
        distinguishable**, which is the whole reason $0 is recorded rather than skipped.
  - ✅ A3.2 `0.00092 + 0.000924 = 0.001844` — accumulation is exact. The breaker can now
        actually trip, which it could not have done at any limit before today.


---

## PHASE 11 · B · RESULT — `docs/INSPECTION.md`, 454 lines, 2026-09-07

- ✅ **B1 Instrument primer** — four tools, four questions, real ports (3009/3010/3007/3013).
- ✅ **B1.3 THE ASYNC CAVEAT, up front** — this is the fact that would have made the whole
      document wrong if copied from the reference project's shape:
  - ✅ B1.3a **TWO metrics endpoints.** `tp-api` carries only `tp_dispatch` and
        `tp_rate_limit_events`; **everything else is on the WORKER** (`worker:3005`).
        Reading only the API and concluding "nothing is recorded" is the commonest mistake.
  - ✅ B1.3b **TWO Jaeger services.** One plan = two traces. A near-empty `tp-api` trace is
        CORRECT — the pipeline lives under `tp-worker`.
  - ✅ B1.3c Langfuse is an **OTel exporter on the same TracerProvider**, not a second SDK.
- ✅ **B2 18 queries**, each naming its component and its expected desired-state response,
      with a "plausible-looking failure" for each so a pass cannot be faked by eye.
- ⚠️ **B2.x A finding worth its own line: `venues: []` is EVIDENCE.**
      Measured on a not-found city AND on an injection-shaped city name: `venues=[]`,
      `cost=$0.00`, no LLM call at all. That empty list is this app's equivalent of "a
      refusal has no generate span" — it proves nothing was spent. An itinerary that
      arrived WITH `venues: []` would mean text produced with no model behind it.
- 📝 **B3 A PREMISE IN THE BRIEF WAS WRONG, and the document now says so.**
      The brief assumed a repeated query is served from cache without an LLM call. **There
      is no response cache in this app.** Measured: the same query twice produced two
      `run_id`s and two LLM calls; only `geo` and `wx` lookups were reused.
  - ✅ B3.1 Consequence for deliverable E: clearing the cache changes external lookups, and
        **never** changes whether the model runs or what it costs. Documented as §0.3
        rather than left as a false expectation.
- ✅ **B4 Every query labelled** *retrieval quality* vs *corpus coverage*, because the
      corpus holds five cities and conflating the two is how you conclude retrieval is
      broken when it was merely unasked.
- ✅ **B5 Verified: all 16 emitted metrics are cited, and every metric cited is emitted.**
      Checked mechanically against `metrics.py`, not by eye.
  - ⚠️ B5.1 The checker first flagged `tp_retrieval` as fictional. It was matching
        `tp_retrieval.vectorstore` — a Python MODULE PATH, not a metric. Instrument bug,
        not a document bug; the regex now excludes names followed by a dot.
  - ✅ B5.2 It also found three emitted metrics the draft never cited
        (`tp_run_duration_seconds`, `tp_run_cost_usd`, `tp_venue_latency_seconds`). Added
        to Q1 and Q14 where they belong, with the distinction stated: run duration covers
        the whole pipeline, venue latency covers ONE call, and only the latter can name a
        slow leg.

### Real shapes captured for the document (not estimated)
| query | venues | cost | grounded | outcome |
|---|---|---|---|---|
| Kyoto, temples+food | `['local-sglang']` | $0.00 | True | 5 items, 0 warnings |
| Zzyzxville | `[]` | $0.00 | False | honest "could not find" |
| injection-shaped city | `[]` | $0.00 | False | treated as a place name, **zero spend** |


---

## PHASE 11 · C · RESULT — `docs/INSPECTION_DEEP.md`, 563 lines, 2026-09-08

**Verified mechanically, not by eye:** 16/16 emitted metrics cited and every cited metric
emitted · **37/37 dashboard panels described**.

- ✅ **C1 Part 0** — four instruments, why they do not overlap, and the async shape.
- ✅ **C2 Part 1 — all 16 metrics.** Each carries: what it IS · what it TELLS you · WHY it
      exists · exact PromQL · bad values · **which endpoint it lives on** · its gotchas.
  - ✅ C2.4 Counter vs gauge vs histogram explained first, including that
        `histogram_quantile` INTERPOLATES inside a bucket, so any percentile built on under
        ~20 samples is noise.
  - ✅ C2.5 Named the trap that `tp_run_duration_seconds` **mixes venues** — it moves when
        the CHAIN SHIFTS rather than when performance changes, and can never name the slow
        leg. That is what `tp_venue_latency_seconds` exists for.
- ✅ **C3 Part 2 — all 37 panels** across the 5 sections, with the four reading concepts
      first (stat vs timeseries · thresholds ARE the verdict · what `rate()` does at idle ·
      counters reset on restart).
  - ⚠️ C3.1 The coverage check flagged 4 panels as undocumented. They WERE described, but
        under paraphrased titles (`Run p50 (< 20s)` vs the dashboard's `Run p50 (NFR <
        20s)`). Cosmetic in prose, real in practice: a reader cannot find a panel whose name
        does not match. Titles now match the dashboard exactly.
- ✅ **C4 Part 3 — Jaeger from zero**, written against a REAL captured trace.
  - ✅ C4.2 The waterfall: **horizontal is time, vertical is NESTING, not time.** "A tall
        trace is not a slow trace — tall means many operations, WIDE means slow."
  - ⚠️ C4.6 **This part corrected a claim I had already published in B.** I wrote that a
        plan produces TWO separate traces. It does not: Celery's OTel instrumentation
        propagates context through the queue, so it is **ONE trace of 13 spans spanning both
        services**. Fixed in INSPECTION.md as well as here.
  - ⚠️ C4.3 **The root span is SHORTER than its own child, and that is correct.** Measured:
        `POST /plan` = 38.0 ms, its child `run/...plan_task` = 3685.8 ms — **97x the root**,
        because the HTTP request returns 202 while the task keeps running. Reading the root
        as "the plan took 38ms" understates the app by 100x.
  - ✅ C4.5 **Trace shapes, derived from real data:** 13 spans = grounded (`llm.complete`
        x2); **11 spans = declined, with `llm.complete` entirely ABSENT**. Of 8 recent plan
        traces, 6 were 13-span and 2 were 11-span — and exactly 2 declining plans had been
        run. The shapes matched one-to-one.
        **The absence of `llm.complete` is the Jaeger-side proof of `venues: []`.**
  - ✅ C4.7 Real per-span durations recorded: geocode **2.3 ms** · gather **1194.5 ms** ·
        compose **1985.7 ms** (essentially all of it the LLM call) · critic **339.5 ms**,
        with 33.4 ms unaccounted — small, therefore healthy.
  - ✅ C4.8 Which service to search: `tp-worker` returns ONLY plan traces; `tp-api` also
        returns every `GET /runs/{id}` poll, which swamps the list.
- ✅ **C5 Part 4 — Langfuse**, including the caveat that matters most here: because
      `_build_days()` is deterministic and ungrounded prose is discarded, **a bad answer in
      this app is almost always a RETRIEVAL problem**. The model never writes `items`.
- ✅ **C6 Part 5** — the battery deepened: for each query, the one thing to actually OPEN,
      rather than repeating INSPECTION.md.
- ✅ **C7 Part 6** — the failover drill for both engines, with the two traps that make a
      drill lie: an unverified fault injection, and a leg made ABSENT (config removal) which
      tests configuration rather than resilience.


---

## PHASE 11 · C & D · RESULT — completed in a parallel session, verified here 2026-09-08

### ✅ C · `docs/INSPECTION_DEEP.md` — 563 lines, all six parts present
- ✅ **C1 Part 0** — four instruments, why they do not overlap
- ✅ **C2 Part 1 — all 16 metrics** (§1.0 types · §1.1 outcome · §1.2 latency · §1.3 cost · §1.4 health)
  - ✅ C2.1 per metric: what it IS · what it TELLS · WHY it exists
  - ✅ C2.2 exact PromQL + which endpoint (api vs worker)
  - ✅ C2.3 bad values + gotchas (empty / NaN / counter reset)
  - ✅ C2.4 counter vs gauge vs histogram explained (§1.0)
- ✅ **C3 Part 2 — all 37 panels across the 5 sections** (§2.1-§2.5, counts stated per section:
      6 stats · 16 stats + 2 timeseries · 4 · 5 · 4)
  - ✅ C3.1 stat vs timeseries; thresholds are the verdict (§2.0)
  - ✅ C3.2 why §0 uses `rate()` but the venue rows are cumulative
  - ✅ C3.3 "not served since restart" = an UNTESTED fallback, not missing data
- ✅ **C4 Part 3 — Jaeger from zero**
  - ✅ C4.1 what a span/trace IS (§3.1)
  - ✅ C4.2 waterfall axes — horizontal = time, vertical = NESTING not time (§3.2)
  - ✅ C4.3 children do not sum to the parent; the unaccounted gap (§3.4)
  - ✅ C4.4 every span in this app + typical duration (§3.7)
  - ✅ C4.5 trace shapes + absent spans as evidence (§3.5)
  - 📝 C4.6 **My earlier claim was WRONG and the parallel session corrected it.** I wrote
        that one plan produces TWO separate traces. It does not: Celery's OTel
        instrumentation propagates trace context through the queue, so a plan is **ONE
        trace of 13 spans spanning both services** (§3.6). Either service finds the whole
        thing.
  - ⚠️ C4.6a And it found the consequence I had missed: **the root span is SHORTER than
        its own child.** Measured — `POST /plan` 38.0 ms, `run/plan_task` 3685.8 ms, 97x
        the root. In a synchronous app a child can never outlive its parent; here the HTTP
        request returns 202 while the task runs on. **Reading the root duration as "the
        plan took 38 ms" understates the app by 100x** (§3.3).
- ✅ **C5 Part 4 — Langfuse** (§4.1 what it is · §4.2 trace vs observation · §4.3 fault
      attribution · §4.4 the structural-grounding caveat)
- ✅ **C6 Part 5** — the battery, deepened
- ✅ **C7 Part 6** — the failover drill, both engines

### ✅ D · Two scripts — 665-line shared module, two 18-line entrypoints
- ✅ **D1 `scripts/_inspect_common.py`** carries ALL logic, engine-parameterised
- ✅ **D2/D3** `inspect_stack_sglang.py` and `inspect_stack_vllm.py` are thin by design —
      two near-identical copies would drift the first time either was touched
- ✅ **D4 DNS blackhole, never config removal** — `HOSTS` maps each leg to a hostname
      (`sglang`, `vllm`, `api.groq.com`, `api.openai.com`); removing a leg from the chain
      would make it ABSENT, which tests configuration rather than resilience
- ✅ **D5 Every injection is VERIFIED, and an unverified one is VOID** — `POOL_DRAIN_S = 8.0`
      lets the pooled socket expire, then resolution is re-checked from INSIDE the worker;
      if the host does not resolve to loopback the step is recorded as void with
      "does not resolve to loopback", never as a pass. An unverified injection turns a
      green result into a lie.
- ✅ **D6 Cache cleared between steps** so a repeat is not served from a tool cache
- ✅ **D7 The full ladder** engine -> groq -> openai -> clean failure
- ✅ **D8 Everything else in one run**, including the runtime kill switch asserting 503
- ✅ **D9 `finally:` restores state ALWAYS**, including on exception — `/etc/hosts` cleaned
      and the kill switch cleared, because a drill that leaves a blackhole behind has
      broken the app it was inspecting

---

## PHASE 11 · D · EXECUTION RESULT — the scripts were RUN, 2026-09-08

> The `D` block above was written by reading the code. This block was written by running it.
> They disagreed, and running won. **📝 The D9 claim above ("`finally:` restores state
> ALWAYS") was false when written** — the restore had never once worked.

### ✅ D10 · First end-to-end execution — `PASS=56 · FAIL=1`

| # | Sub-step | Status | Evidence |
|---|---|---|---|
| D10.1 | `inspect_stack_sglang.py` runs to completion | ✅ | `EXIT=1`, 57 checks reported |
| D10.2 | Ladder rung 1 — engine serves | ✅ | `venues=['local-sglang'] cost=$0.0` |
| D10.3 | Cost attribution for a self-hosted leg | ✅ | `$0.00 (self-hosted, RECORDED not skipped)` |
| D10.4 | Rung 2 — engine down -> groq | ✅ | `venues=['groq'] cost=$0.002064` |
| D10.5 | Rung 3 — engine + groq down -> openai | ✅ | `venues=['openai'] cost=$0.002295` |
| D10.6 | Rung 4 — all legs down -> DECLINE, never fabricate | ✅ | `status=failed venues=[]` |
| D10.7 | Recovery after cooldown | ❌ -> ✅ | `still not serving after 90s` — **my leftovers** |

### ⚠️ D11 · Three defects in my own instrument, found by running it

**D11.1 — the sed program was not a sed program.**
`pat = "/;/".join(HOSTS.values())` produced
`sed -i '/sglang/;/api.groq.com/;/api.openai.com/d'`.

```
$ docker exec p3-ai-travel-planner-worker-1 sh -c "sed -i '/sglang/;/api.groq.com/;/api.openai.com/d' /etc/hosts"
sed: -e expression #1, char 9: unknown command: `;'
exit=1
```

**D11.2 — `sed -i` cannot edit `/etc/hosts` in a container at all.** It is a bind mount
from the daemon; sed writes a temp file beside the target and renames it over, and the
rename is refused. So even a *correct* expression would have removed nothing:

```
$ docker exec p3-ai-travel-planner-worker-1 sh -c "sed -i '/sglang/d' /etc/hosts"
sed: couldn't open temporary file //etc/sed8NWGJ2: Permission denied
exit=4
```

**D11.3 — the `finally:` block ANNOUNCED a restore it never checked.** It printed
`state restored: /etc/hosts cleaned` unconditionally. The truth after two runs:

```
127.0.0.1 sglang
127.0.0.1 sglang
127.0.0.1 api.groq.com
127.0.0.1 sglang
127.0.0.1 api.groq.com
127.0.0.1 api.openai.com
```

Every leg blackholed, in a worker the drill had declared clean. **Any real plan run in
that window would have failed**, and the report would still have been green. This is
precisely the failure the block exists to prevent — a drill that breaks the app it
inspects and then certifies the app.

Why the ladder rungs were still valid: injections *accumulate* monotonically, and the
ladder's intended states are also monotonic (`{}` -> `{engine}` -> `{engine,groq}` ->
`{all}`). The rungs held by luck, not by design. Only recovery and the trailing readings
were poisoned.

### ✅ D12 · Fixed and PROVEN against the state the old code could not clean

- ✅ `blackhole()` now **raises** on a non-zero exit instead of failing silently
- ✅ `unblackhole_all()` filters to `/tmp` then `cat`s back through a redirect —
      redirection truncates the existing inode in place, which a bind mount permits
- ✅ It **returns a verified boolean** (`not any(injection_landed(h) ...)`)
- ✅ `finally:` now reports the truth, and on failure records `r.bad(...)` with the
      by-hand repair command instead of printing reassurance

```
BEFORE (True = worker cannot reach it): {'sglang': True, 'vllm': False, 'api.groq.com': True, 'api.openai.com': True}
AFTER : {'sglang': False, 'vllm': False, 'api.groq.com': False, 'api.openai.com': False}
unblackhole_all() returned: True
PROVEN: a state the old restore could not clean is now clean
```

### ✅ D13 · Re-run — `EXIT=0 · PASS=57 · FAIL=0`

```
ok   all legs down -> clean failure  |  status=failed venues=[]
ok   local-sglang reclaims traffic after cooldown  |  recovered
ok   every panel query executes  |  37 panels, 0 errors
ok   venue breakers closed  |  {'local-sglang': '0', 'groq': '0', 'openai': '0'}
  state restored: /etc/hosts cleaned (VERIFIED), kill switch cleared
```

The recovery FAIL was **entirely my leftovers**. The chain reclaims its engine correctly.

### ⚠️ D14 · `inspect_stack_vllm.py` — ran, and exposed two more instrument defects

First run: `PASS=50 SKIP=2` — correct to SKIP (`tp-vllm` is profile-gated and not up).
But it was **quietly dishonest** in two ways:

- ⚠️ **D14.1** It printed a green `ok worker container sees a chain | local-sglang,groq,openai`
      under a banner reading `chain local-vllm -> groq -> openai`. Green, while the
      subject of the run was not in the live chain at all.
      **Fixed:** now `warn local-vllm is in the LIVE chain | worker chain is
      'local-sglang,groq,openai' — this run inspects THAT chain; the local-vllm leg is
      NOT exercised.`
- ⚠️ **D14.2** The hint said `make vllm-up`, which starts the **engine** but leaves
      `SERVING_CHAIN=local-sglang` — you would get a running vLLM that never receives a
      request. **Fixed:** the hint is now `make up-vllm`, which also sets the chain.

Re-run: `PASS=50 SKIP=2 WARN=1`.

### ⏳ D15 · The vLLM LADDER has still never been exercised — honestly pending

`local-vllm` has never served a request through the chain. Proving it needs the engine
up **and** routed to: `make up-vllm`. Recorded as ⏳, not ✅.

### 📌 D16 · Unattributed, stated as fact only

`tp-sglang` was serving at 06:20 (`ok local-sglang running | Up 30 minutes (healthy)`)
and by ~06:30 was absent from `docker ps -a`; `sglang` no longer resolves inside the
worker. What is provable: the inspection scripts never stop or remove a container
(`grep` finds no `docker stop|rm|kill`), and `sglang-up` does not use `--rm`.
`docker events` retains no lifecycle history on this daemon (zero start events for
containers that demonstrably started inside the window), so **the cause is not
attributable and I am not guessing at one.**

What it did demonstrate, unplanned: the engine vanished mid-session and the app kept
answering — `venues=['groq']`. That is the failover working in production conditions
rather than in a drill. Bring the engine back with `make sglang-up`.


---

## PHASE 11 · E · RESULT — cache clearing, RUN not just written, 2026-09-08

The targets existed from the Makefile rework but **had never been executed once**. Running
them is what turned them from plausible into proven — and found one real gap.

### ✅ E1 · `cache-prefix` / `cache-ls` / `cache-clear` on the REAL key shape

```
$ make cache-prefix
v1.v1.v1

$ make cache-ls
  prefix: v1.v1.v1
    v1.v1.v1:geo:kyoto
    v1.v1.v1:wx:35.0116:135.7681:1
  2 cached lookup(s)
```

The prefix is **computed by the running worker** (`cache_version()`), never hard-coded —
a literal `v1.v1.v1` would silently clear nothing the moment anyone bumped a version.

### ✅ E1.1 · Proven SURGICAL — it clears cache and nothing else

```
### BEFORE                          ### AFTER
  cache keys: 2                       cache keys: 0
  spend spend:usd:2026-09-08 =        spend spend:usd:2026-09-08 =
        0.0122262                           0.0122262      <- unchanged
  celery result keys: 38              celery result keys: 38   <- unchanged
```

This matters because the same Redis is broker, result backend, spend accumulator and
rate-limit store. `FLUSHDB` would destroy the queue and the cost control; every target is
scoped to the prefix.

### ✅ E1.2 · Proven to make a repeated query genuinely FRESH — the actual requirement

Measured on `tp_cache_events_total`, same query three times:

```
run 1 after clear      : {('geo','miss'): 1.0, ('wx','miss'): 1.0}
run 2 WITHOUT clear    : {('geo','hit'):  1.0, ('wx','hit'):  1.0}
run 3 after cache-clear: {('geo','miss'): 1.0, ('wx','miss'): 1.0}
```

Miss -> hit -> miss. The cache is doing its job, and the clear command undoes it exactly.

### ⚠️ E2 · GAP FOUND — `runs-clear` orphaned the LangGraph checkpoint tables

`runs-clear` truncated `runs` only. The DB actually holds four more tables:

```
runs               157
checkpoints       2144   (344 distinct thread_id)
checkpoint_writes 5943
checkpoint_blobs  3365
```

Of 2144 checkpoint rows, only 886 join to a surviving run — the rest were already
unreachable garbage, and the tables grow without bound.

**Does this affect freshness?** No, and that is worth stating precisely rather than
assuming: `thread_id` **is** the run_id (proven by the join), so every run is its own
thread and no checkpoint is ever reused by a later query. Checkpoints are history and
disk, not cache. Only `cache-clear` affects freshness.

- ✅ **Fixed:** `runs-clear` now truncates `runs, checkpoints, checkpoint_writes,
      checkpoint_blobs` together. `checkpoint_migrations` is deliberately left alone —
      schema bookkeeping, not run state.
- ✅ **Falsification-tested** rather than assumed — FKs could have made the truncate fail:

```
BEGIN
TRUNCATE TABLE
 truncate accepted, rows now: 0
ROLLBACK
$ select count(*) from runs;  ->  157      <- nothing was actually lost
```

### ✅ E2.1 · New `make state-ls` — see it before you delete it

```
$ make state-ls
    runs                 157 rows
    checkpoints          2144 rows
    checkpoint_writes    5943 rows
    checkpoint_blobs     3365 rows

  checkpoints are LangGraph state, keyed by thread_id = the run_id.
  Every run is its own thread, so they NEVER make a repeated query stale;
  they are history and disk, not cache. 'make cache-clear' is what makes
  a repeat query fresh.
```

### ✅ E2.2 · `make metrics-note` — the honest limit, verified

Prometheus counters cannot be reset in place; the only reset is restarting the exporting
process (`make up-app`). The command says so rather than pretending otherwise, and
explains why the dashboard reads "not served since restart" instead of "no data".

### ✅ E3 · The caching FEATURE was not removed — only commands added

```
$ git status --porcelain | grep -i cache
  (no cache source file modified)
```

All five targets are discoverable in `make help`: `cache-prefix`, `cache-ls`,
`cache-clear`, `state-ls`, `runs-clear`, `metrics-note`.

### ✅ E4 · Application verified unharmed after every change in this phase

```
hosts clean? {'sglang': False, 'vllm': False, 'api.groq.com': False, 'api.openai.com': False}
status  : succeeded
venues  : ['groq'] cost=$0.000864
grounded: True days: 2
```



---

## PHASE 11 · E · RESULT — cache clearing, 2026-09-08

**Gate:** ruff clean · mypy --strict clean on 59 files · **184 passed** · app serving.

- ⚠️ **E.0 The docs referenced targets that did not exist.** Both `INSPECTION.md` and
      `INSPECTION_DEEP.md` told the reader to run `make cache-clear`. There was no such
      target. Documentation ahead of the Makefile is the same class of defect as a
      dashboard panel with no metric behind it.
- ✅ **E1 Five targets added** — `cache-prefix`, `cache-ls`, `cache-clear`, `runs-clear`,
      `metrics-note`.
  - ✅ E1.1 **The prefix is ASKED FOR, never written down.** `make cache-prefix` runs
        `cache_version()` inside the live worker. A literal `v1.v1.v1` in the Makefile
        would go stale the first time anyone bumped a version and would then silently
        clear nothing while appearing to work.
  - ⚠️ E1.2 **A naive implementation would have broken the app.** This Redis is not only a
        cache — a live scan found the spend accumulator, the Celery result backend, the
        Kombu broker bindings and the rate-limit windows sharing it. `FLUSHDB` destroys
        the task queue AND the cost control. Every target is scoped to the version prefix.
  - ✅ E1.3 **Verified against live Redis, not asserted:**

    | | before | after |
    |---|---|---|
    | dbsize | 11 | **9** (exactly the 2 cache keys) |
    | `spend:usd:*` | `0` | **`0`** — survived, still zero rather than nil |
    | `celery-task-meta-*` | 5 | **5** |
    | `_kombu.binding.*` | 3 | **3** |
    | `v1.v1.v1:*` | 2 | **0** |

    A plan run immediately afterwards still succeeded: `venues=['local-sglang']`, 5 items.
- ✅ **E2 Postgres and Prometheus documented honestly**
  - ✅ E2.1 `make runs-clear` truncates `runs`, **prompts first**, and is deliberately NOT
        folded into `cache-clear`: a cache is a performance detail, run history is the
        system of record, and deleting it as a side effect would be a surprise nobody
        asked for. Verified: answering `n` left all 127 runs intact.
  - ✅ E2.2 **Prometheus counters cannot be reset in place, and `make metrics-note` says
        so** rather than offering a command that pretends to. The only reset is restarting
        the exporting process. This is exactly why the venue rows read "not served since
        restart": since-restart is the honest window, not a defect.
- ✅ **E3 The caching feature is untouched** — commands to clear it, nothing removed.
- ✅ **E4 Both documents re-verified**: every `make X` written in a code context now
      resolves to a real target.
  - 📝 E4.1 The checker first flagged `make a`, `make the`, `make an` as missing targets.
        Those are English prose. Same instrument bug as `tp_retrieval.vectorstore` earlier
        — a regex reading documentation as code. Restricted to backticked/code-line
        contexts.

### ⚠️ E.5 A stray `scratchpad/` was left in the project root by the parallel session
- ✅ E5.1 It broke the ruff gate (12 findings) and was **not gitignored**, so it would have
      been committed — 47 KB `Makefile.bak`, probe scripts and run logs.
- ✅ E5.2 **Ignored rather than deleted**, because the logs are evidence: they record the
      two inspection scripts actually running.

  | script | result |
  |---|---|
  | `inspect_stack_sglang.py` | **PASS=57** · 37 panels, 0 query errors · state restored (VERIFIED) |
  | `inspect_stack_vllm.py` | **PASS=50, SKIP=2, WARN=1** · state restored (VERIFIED) |

  Both confirm `tp-api` and `tp-worker` present in Jaeger and all venue breakers closed.

---

## PHASE 11 · D15 · RESULT — the vLLM ladder, EXERCISED, 2026-09-08

Run by the user on their machine. `PASS=57 · FAIL=0`. This is the first time `local-vllm`
has ever served a request through the chain — every earlier vLLM report was a SKIP.

### ⚠️ D15.0 · A defect found on the way: `make up-vllm` re-downloaded a 30 GB image

The recipe printed `pulling image if absent...` and then ran an **unconditional**
`pull --quiet`. On a moving `:latest` tag that is not an "if absent" test at all — docker
re-checks the registry and downloads a whole new image, and `--quiet` hides every byte.

Evidence it was doing nothing useful: the image was already local
(`vllm/vllm-openai:latest`, 30.8 GB, 3 weeks old), the bring-up sat on
`pulling image if absent...` with **no `tp-vllm` container**, GPU flat at ~2.2 GB, and the
image store unchanged at `56 images / 167.1 GB`.

- ✅ **Fixed** for BOTH engines: pull only when `docker image inspect` fails
- ✅ Escape hatch kept: `PULL=1 make up-vllm` forces a refresh
- ✅ The echo no longer lies — `checking image...` then one of two explicit outcomes
- ✅ Proven by the user's own run:

```
  checking image...
  image present, not pulling: vllm/vllm-openai:latest
  weights already complete in p3-ai-travel-planner_tp_hf_cache - nothing to do
  starting vllm; waiting for it to SERVE (not merely to start)...
 ✔ Container tp-vllm Healthy    139.4s
  vllm SERVING on http://localhost:3019/v1
```

📝 I estimated the load at 4–7 minutes; it took **139.4 s**.

### ✅ D15.1 · The D14.1 warning is gone — the run now inspects the chain it names

```
ok   Makefile chain for ENGINE=vllm  |  local-vllm,groq,openai
ok   worker container sees a chain   |  local-vllm,groq,openai
ok   local-vllm running              |  Up 5 minutes (healthy)
```

### ✅ D15.2 · The full ladder, on vLLM

| Rung | Result | Evidence |
|---|---|---|
| engine serves | ✅ | `venues=['local-vllm'] cost=$0.0` |
| cost attribution | ✅ | `['local-vllm'] -> $0.00 (self-hosted, RECORDED not skipped)` |
| engine down -> groq | ✅ | `venues=['groq'] cost=$0.000877` |
| engine + groq down -> openai | ✅ | `venues=['openai'] cost=$0.002405` |
| all legs down -> clean failure | ✅ | `status=failed venues=[]` — declined, did not fabricate |
| recovery after cooldown | ✅ | `local-vllm reclaims traffic after cooldown | recovered` |
| restore | ✅ | `state restored: /etc/hosts cleaned (VERIFIED)` |

Both engines have now been proven end to end: SGLang `PASS=57`, vLLM `PASS=57`.

### ⚠️ D15.3 · The vLLM run exposed a THIRD instrument defect: a green spend check

```
ok   spend key updated by a run  |  0.0155998 -> 0.0155998
```

Green, with a number that never moved. `check_spend_recording` asserted only that the key
**exists** after a run — never that it **grew**. On a local-first chain the serving leg is
self-hosted and costs `$0.00`, so the key *cannot* move, and any stale value from an
earlier paid run keeps the check green permanently.

That is precisely the regression this check exists to catch. The Phase 11 · A defect was
`record_spend()` never being called; if that were reintroduced today, **this check would
still have passed.**

- ✅ **Split into two claims.** Existence is `spend key readable`. Growth is its own line.
- ✅ **Growth is VOID, not PASS, when a free leg served** — `PROVES NOTHING`, with the
      reason: `local-vllm costs $0.00 — a free leg cannot move the key`
- ✅ **Growth is ASSERTED where it can be** — on the ladder's `groq` and `openai` rungs,
      which already run, so no extra fault injection and no extra API spend
- ✅ **Deliberately NOT done:** blackholing the local leg inside the spend check to force
      a paid run. That would push the local venue breaker toward OPEN seconds before the
      ladder's first rung expects that same venue to serve — trading a dishonest check for
      a flaky one
- ✅ **Falsification-tested** — with spend pinned so it cannot move, a paid leg now fails:

```
 FAIL  spend GREW when groq served  |  groq served and cost $0.00088 but spend stayed at 0.0
```

### Running tally of instrument defects found by RUNNING the scripts

| # | Defect | Class |
|---|---|---|
| D11.1 | `sed` expression was not a sed program | silent no-op |
| D11.2 | `sed -i` cannot edit a bind-mounted `/etc/hosts` | silent no-op |
| D11.3 | restore was announced, never verified | **green while broken** |
| D14.1 | chain check passed under a banner naming a different chain | **green while irrelevant** |
| D14.2 | hint started the engine but never routed to it | useless advice |
| D15.0 | `pull --quiet` on `:latest` re-downloaded 30 GB | silent cost |
| D15.3 | spend check proved existence, not growth | **green while blind** |

Five of the seven were green-while-wrong. Reading the code found none of them; running it
found all seven.


### ✅ D15.4 · Confirmation re-run — `PASS=59 · PROVES NOTHING=1 · FAIL=0`

The fix verified in situ, not just in a stub:

```
  ok   spend key readable  |  0.0188824 -> 0.0188824
 VOID  spend GREW on this run  |  ['local-vllm'] costs $0.00 — a free leg cannot move
                                  the key. Growth is asserted on the paid rungs below.

  ok   engine down -> groq             |  venues=['groq'] cost=$0.00092
  ok   spend GREW when groq served     |  0.0188824 -> 0.0198032 (+0.000921)
  ok   engine + groq down -> openai    |  venues=['openai'] cost=$0.002365
  ok   spend GREW when openai served   |  0.0198032 -> 0.0221682 (+0.002365)
```

Same `$0.00` local leg as the run that used to print a false `ok` — now it declines to
claim a pass it cannot earn, and the claim is made where it CAN be earned.

**An unplanned cross-check fell out of this.** The delta written to the breaker's key and
the cost reported to the caller are independent code paths, and they agree:

| Leg | cost reported to the caller | delta written to `spend:usd:*` |
|---|---|---|
| groq | `$0.000920` | `+0.000921` (rounding) |
| openai | `$0.002365` | `+0.002365` (exact) |

Before this, the two could have diverged silently — a run could bill the user one number
while the daily-spend breaker counted another, and nothing would have noticed. That is
now asserted on every paid rung of every inspection run.

### Both engines, both ladders, final state

| Engine | Result | Ladder |
|---|---|---|
| SGLang | `PASS=57 FAIL=0` | local-sglang -> groq -> openai -> decline -> recover |
| vLLM | `PASS=59 PROVES NOTHING=1 FAIL=0` | local-vllm -> groq -> openai -> decline -> recover |


---

## PHASE 12 · K · kind wired into the composite lifecycle, 2026-09-08

Triggered by the user comparing this Makefile against a reference from another project
(supplied as a FEATURE guide only — none of its data, names or paths were copied).

### Verified state BEFORE the change

| Target | kind behaviour | Verdict |
|---|---|---|
| `full` | nothing | correct — documented "no kind/k8s" |
| `up` | calls `infra` -> creates cluster | already right |
| `bootstrap` | nothing | correct — data/app only |
| `upv` | **nothing** | ⚠️ GAP |
| `down` | calls `infra-down` -> **deletes** cluster | inconsistent (see below) |
| `downv` | **nothing at all** | ⚠️ GAP |
| `KIND=0` | did not exist | ⚠️ GAP |
| `kind-status` / `kind-stop` | did not exist | ⚠️ GAP |

📝 On the report that "the cluster remains after `make down`": the recipe *did* call
`infra-down`. Two things make that consistent with what was seen — `make full` never
creates a cluster, so `down` has nothing to delete; and `make downv` genuinely did not
touch kind at all.

### ✅ K0 · SAFETY FIRST — can this Makefile harm another project's cluster?

**No, and it was checked before anything was wired.** `scripts/kind-down.sh` resolves
`CLUSTER="${KIND_CLUSTER_NAME:-voyantra}"` from `.env` and matches with `grep -qx`, then
deletes **by name**. Another cluster on the same machine cannot be selected. Every new
target below uses the same name resolution.

Proven live, with the other project's cluster running at the time:

```
### BEFORE                          ### AFTER
  cluster: medbot                     cluster: medbot
  medbot-worker       | Up 7 hours    medbot-worker       | Up 7 hours
  medbot-worker2      | Up 7 hours    medbot-worker2      | Up 7 hours
  medbot-control-plane| Up 7 hours    medbot-control-plane| Up 7 hours
```

### ✅ K1 · `KIND ?= 1` knob

`KIND=0` makes every composite target ignore Kubernetes.

```
$ make kind-stop KIND=0
  KIND=0 - skipping kind
```

### ✅ K2 · `kind-start` — create if absent, else RESTART stopped nodes

⚠️ **`make infra` alone could never recover a STOPPED cluster.** kind still lists a
cluster whose nodes are stopped, so `kind-up.sh` takes its "already exists" branch and
then runs `kind load` and `helm upgrade` against a dead API server. `kind-start` now
starts the node containers first, re-exports kubeconfig (a restarted control-plane gets a
NEW API-server port, and the stale config fails with "current-context is not set" — which
reads like a broken cluster rather than a stale pointer at a healthy one), and waits for
node readiness before delegating.

### ✅ K3/K4 · `kind-stop` (preserves) and `kind-status`

```
$ make kind-status
  no kind cluster 'voyantra' - 'make kind-start' creates one
$ make kind-stop
  kind: no cluster 'voyantra' - nothing to stop
```

### ✅ K5 · Wired into the lifecycle

| Target | now does |
|---|---|
| `up` | `kind-start` |
| `upv` | `kind-start` **(new)** |
| `down` | `kind-stop` — nodes stopped, **cluster preserved** (was: delete) |
| `downv` | `kind-down` — cluster deleted **(new)** |
| `full` | still nothing — that is the whole difference between `full` and `up` |

📝 **`down` changed from delete to stop.** Deleting was the one inconsistent thing it
did: `down` keeps every compose data volume, stopping the node containers frees the same
RAM, and preserving turns the next `up` from a ~2 minute recreate into seconds. Deletion
moved to `downv`, the destructive verb — matching the supplied reference.

### ✅ K6 · `infra` / `infra-down` kept as aliases
Older docs, scripts and muscle memory still work.

### ⏳ K7 · NOT yet proven — stated honestly

`kind-start` has never been executed, and `kind-stop` has never run against a LIVE
`voyantra` cluster. Both are only proven on the no-cluster path. Creating the cluster
builds three images (`tp-api`, `tp-worker`, `tp-web` at tag `p61`) if absent, so it is a
10-25 minute operation and was not run unasked.

Prove it with:  `make kind-start` then `make kind-status`, then `make down` and confirm
`kind get clusters` still lists `voyantra` while its nodes are stopped.


---

## PHASE 12 · T0 · Additive Makefile targets, 2026-09-08

21 new targets. **No existing target was changed** — that is what made this the zero-risk
tier. Every value was read out of the repo, not assumed: the kill-switch key from
`control.py:75`, the image tag from `scripts/kind-up.sh`, the weight volume, the helm
values path, the terraform directory (`infra/terraform`, not `infra/terraform/aws`).

### ⚠️ T0.0 · A defect I introduced and caught in the same session

`kill-status` reported the switch as ENABLED while Redis was unreachable:

```
$ make kill-status            # entire stack down, 0 containers running
  ENABLED  - no runtime override set
  floor: LLM_ENABLED=true
```

The `exec` failed with "service redis is not running", stderr went to `/dev/null`, and
the empty result fell into the same branch as *"no key set"*. **Absent and unreachable
are not the same answer**, and this is the one command that has to be trustworthy during
an incident — the same green-while-blind class as D15.3.

`kill-on` / `kill-off` were never affected: both fail loudly with exit 1.

- ✅ Fixed: a `redis-cli ping` gate runs first.
- ✅ Falsified — the identical command, same stack state:

```
$ make kill-status
  UNKNOWN - redis is not reachable, so the switch cannot be read.
  Start the data tier first:  make up-data
make: *** Error 1
```

### Status of all 21 targets

| Target | Status | Evidence |
|---|---|---|
| `kill-on` / `kill-off` | ⏳ | needs the stack up |
| `kill-status` | ✅ | UNKNOWN path proven; ENABLED/DISABLED paths need the stack |
| `inspect` (bad ENGINE) | ✅ | `ENGINE=both has no inspection script` + exit 1 |
| `inspect` / `-sglang` / `-vllm` | ⏳ | needs the stack up |
| `smoke` (+ `scripts/smoke.py`) | ⏳ | needs the stack up; `ruff` clean |
| `weights-status` | ✅ | `volume: p3-ai-travel-planner_tp_hf_cache` · `6.1G on disk` · no `.incomplete` |
| `weights-ensure` | ⏳ | not run — may fetch 5.5 GB |
| `gpu` / `gpu-down` | ⏳ | not run — would start/stop the engine |
| `cache-flush` | ⏳ | not run — destructive by design |
| `tf-init` | ⏳ | not run |
| `tf-validate` | ✅ | `Success! The configuration is valid.` |
| `tf-plan` | ⏸️ | needs AWS credentials (R4.2 still paused) |
| `chart-lint` | ✅ | `1 chart(s) linted, 0 failed` + census: 5 Deployments, 4 Services, 1 ConfigMap, 1 Secret, 1 PVC |
| `images` | ⏳ | not run — three image builds |
| `clean-images` / `clean-all` | ⏳ | not run — destructive |
| `langfuse` | ✅ | prints port 3013 + the one login |
| `service_ls` | ✅ | prints local dev credentials only |

### Two deliberate departures from the supplied reference

1. **`clean-images` does NOT delete the vLLM/SGLang images.** Those are upstream images
   shared with other work on this machine; removing them would cost an unrelated project
   an ~83 GB re-pull. They must be removed by hand, on purpose.
2. **`service_ls` never prints provider API keys.** It prints local dev credentials
   (Postgres, dev web login, Langfuse) and the serving chain. `OPENAI_API_KEY`,
   `GROQ_API_KEY` and the rest are excluded by design — a target that echoes real keys
   into a terminal, a screen share or a scrollback is a liability, not a feature.

### 📌 Stack state observed during this work

The P3 stack is **down** — 0 containers, and `tp-vllm` shows `Exited (137)` (SIGKILL).
That is what exposed T0.0. Not attributed: nothing in this session stopped it.


---

## PHASE 12 · T1 · Four safety guards on existing targets, 2026-09-08

These modify targets the whole stack depends on, so each was grounded in the repo first
and then proven by running it.

### ✅ T1.4 · GPU auto-detect — a chain must not NAME a venue that cannot answer

`GPU ?= $(shell nvidia-smi -L ...)`, with an override applied AFTER the ENGINE block so
it beats every ENGINE choice — on a machine with no card that choice cannot be honoured.

```
  ENGINE=sglang GPU=1 chain=local-sglang,groq,openai profile=[--profile gpu-sglang]
  ENGINE=sglang GPU=0 chain=groq,openai              profile=[]
  ENGINE=vllm   GPU=0 chain=groq,openai              profile=[]     <- override wins
```

Why it matters beyond tidiness: a chain that lists a dead local leg pays that leg's
connect timeout on EVERY request before failing over, and the breaker only shortens that
after three failures have already been paid for. `make up GPU=0` also gives a no-card
dry run on a machine that has one.

### ✅ T1.1 · `up-app` validates SERVING_CHAIN with the REAL parser

Uses `tp_core.llm.venues.parse_chain` — the same function the app boots with, so the
check can never disagree with what is enforced.

```
$ make up-app ENGINE_CHAIN=sglang,groq

  REFUSING TO START THE APP TIER: SERVING_CHAIN is not valid.

      chain: sglang,groq
      tp_core.exceptions.ConfigError: chain entry 'sglang' is an ENGINE, not a venue.
      Engines only exist on the local venue, so write 'local-sglang' ...

make: *** [up-app] Error 1

  (app containers running: 0)      <- refused BEFORE starting anything
```

This is the failure that previously reached you as docker's useless
"dependency failed to start".

⚠️ **A broken preflight must never block the app.** Only a genuine `ConfigError` refuses;
if the parser cannot be run at all (no uv, package not installed) it prints
`(chain preflight skipped - the parser could not be run)` and continues. A guard that can
take the application down when the guard itself is broken is worse than no guard.

### ✅ T1.2 · `up-app` reports the corpus — and WARNS rather than refuses

```
$ make up-app
  corpus: 26 points in 'pois'
```

Unreachable branch, same logic against a dead port:

```
  corpus: qdrant not reachable yet - check skipped
```

📝 **Deliberately weaker than the reference Makefile, for a reason found by reading
first.** That one REFUSES to start the app on an unindexed corpus. Here, `bootstrap` and
`upv` both run `up-app` BEFORE `seed` — so refusing would have broken the documented
from-scratch path outright. It warns loudly instead, and says exactly why an empty corpus
is dangerous: every plan declines with `venues=[]`, which is indistinguishable from the
app honestly refusing an unknown city.

### ⚠️ T1.3 · Prometheus reload — the guard would have been a NO-OP as designed

The obvious implementation (POST `/-/reload` in `up-obs`) **could not have worked**: the
`prometheus` service declared no `command:`, so it ran the image default, which does not
include `--web.enable-lifecycle`. That endpoint answers **405**, and a blind POST would
have reported success on nothing — the same green-while-wrong class as D11.3 and D15.3.

- ✅ `docker-compose.observability.yml` now sets `command:` with the image's two REAL
      defaults (`--config.file`, `--storage.tsdb.path`, read from
      `docker image inspect`, not guessed) plus `--web.enable-lifecycle`. Declaring
      `command:` replaces the default entirely — omitting either would have left
      Prometheus with no config file or no storage path.
- ✅ `up-obs` CHECKS the HTTP status and names each outcome, including the 405 case.

```
$ make up-obs
  prometheus: scrape config reloaded

$ curl -X POST http://localhost:3009/-/reload   ->  HTTP 200
$ prometheus targets: prometheus=up            <- not broken by the command: change
```

Why this matters: `prometheus.yml` is bind-mounted, so `compose up` sees no container
change and keeps the OLD config. Editing the scrape config and running `make up` was a
silent no-op.

### T0 items closed now that the stack is up

| Item | Status | Evidence |
|---|---|---|
| `kill-on` | ✅ | `DISABLED - planning:enabled=0` -> `POST /plan HTTP 503` |
| `kill-off` | ✅ | `ENABLED - no runtime override` -> `POST /plan HTTP 202` |
| `kill-status` both live paths | ✅ | DISABLED and ENABLED, plus the UNKNOWN path proven earlier |
| `smoke` | ✅ | see below |

```
$ make smoke
SMOKE - two plans against http://localhost:3004

  in-corpus Kyoto          status=succeeded  venues=['groq'] grounded=True  days=1 cost=$0.000731
  off-corpus Zzyzxville    status=succeeded  venues=[]       grounded=False days=0 cost=$0.0

  PASS  grounded where it can be, declined where it cannot.
        venues=[] on the second run is the proof no model was called.
```

Note `venues=['groq']`: no local engine is running, so the chain failed over exactly as
designed — and `make smoke` says so instead of hiding it.


---

## PHASE 12 · T0 completion + defects #8-#11, 2026-09-08

Four more instrument defects, all surfaced by the stack being in states the drill had
never met. None were findable by reading the code.

### ⚠️ Defect #8 · The drill would have BLAMED THE APP for its own broken environment

The stack was torn down mid-run. `spend_now()` did `float(v)` unconditionally and died:

```
ValueError: could not convert string to float:
'Error response from daemon: No such container: ...-redis-1'
```

An entire inspection aborted by a traceback. But the traceback was the *lesser* problem.
Returning `0.0` there — the obvious "fix" — would have been far worse: the ladder would
then have compared `0.0` to `0.0` and reported

```
FAIL  spend GREW when groq served — record_spend() is not being called
```

which is a **false accusation against working code**, naming the exact Phase 11 · A bug
that was already fixed. Chasing a regression that does not exist costs more than missing
one that does.

- ✅ `spend_now()` returns `None` when the value cannot be READ (unreachable != zero)
- ✅ `check_spend_recording` -> `VOID redis could not be read — the stack is not up`
- ✅ ladder rungs -> `VOID redis could not be read around this rung`
- ✅ `check_kill_switch`: HTTP `0` means *nothing answered*, so it no longer reports
      `FAIL ... generation was NOT stopped` — it reports
      `VOID API did not respond — is the app tier up?`

### ⚠️ Defect #9 · The ENGINE was not part of the lifecycle (reported by the user)

`tp-sglang` survived `make down`, holding ~6.7GB of VRAM while appearing to be gone.
Three of the four lifecycle targets ignored the engine completely:

| Target | Before | Now |
|---|---|---|
| `up` | `up-engine` | unchanged |
| `upv` | **nothing** | `up-engine`, BEFORE the app tier |
| `down` | **nothing** | `down-engine` |
| `downv` | **nothing** | `down-engine` |

**Nothing is deleted.** `down-engine` runs `compose stop`: container kept, 52GB image
kept, weight cache kept. `make clean-models` remains the only thing that removes weights.

`upv` starts the engine BEFORE the app for the reason `up` already documents: bring the
app up first and its opening requests hit a venue still loading weights, fail the local
leg, trip the breaker, and get served by a hosted venue — the silent failover this chain
exists to expose.

### ⚠️ Defect #10 · A message that was true and useless

`sglang does not resolve to loopback` reads like the app's DNS is broken. The real cause
took a container inspection to find:

```
worker started: 2026-09-08T08:00:08Z   restarts: 0     <- CREATED during the run
run finished:   2026-09-08T08:03:57Z
```

`RestartCount 0` with a start time inside the run window means the worker was not
restarted but **replaced**. A new container gets a fresh `/etc/hosts`, so the injection
went with the old one. The guard did its job — it voided instead of passing — but named
the symptom, not the cause.

- ✅ `_why_injection_vanished()` now distinguishes: container gone / container
      RECREATED (with both short ids) / same container so the append itself failed
- ✅ the banner prints `worker container at start: <id>` so the comparison is visible

**Operational rule this establishes:** the drill needs EXCLUSIVE use of the stack. It
blackholes DNS inside a live container; any concurrent `make up`/`make down` silently
invalidates it. Three runs died to this.

### ⚠️ Defect #11 · `make inspect` was ALWAYS red

`PASS=59 FAIL=0` and it still exited 2. `Report.failed` counted every `PROVES NOTHING`
as a failure — including the spend-growth void, which on a local-first chain happens on
**every healthy run**, because $0.00 cannot grow.

A command that is permanently non-zero on a healthy system is the same disease as a green
check that proves nothing, inverted: an exit code nobody reads. It would also have failed
any CI job it was wired into.

- ✅ `void(..., expected=True)` for STRUCTURAL voids only — exactly one call site
- ✅ they are NOT hidden: still printed inline as `VOID`, and listed under
      `PROVES NOTHING, by design (not failures):`
- ✅ every other void still fails the run (redis unreachable, API silent, injection
      vanished, injections did not land)
- ✅ falsification-tested:

```
  expected-only  -> exit 0
  unexpected     -> exit 1
```

### ✅ T0.2b · `make inspect` — final, on a stable stack

```
ok   engine serves                    venues=['local-sglang'] cost=$0.0
ok   cost attribution                 ['local-sglang'] -> $0.00 (self-hosted, RECORDED not skipped)
ok   engine down -> groq              venues=['groq']   cost=$0.000844
ok   spend GREW when groq served      0.0035233 -> 0.0043673 (+0.000844)
ok   engine + groq down -> openai     venues=['openai'] cost=$0.002523
ok   spend GREW when openai served    0.0043673 -> 0.0068898 (+0.002522)
ok   all legs down -> clean failure   status=failed venues=[]
ok   local-sglang reclaims traffic after cooldown  |  recovered
     state restored: /etc/hosts cleaned (VERIFIED), kill switch cleared

  PASS=59   PROVES NOTHING=1 (by design)      EXIT=0
```

### Running tally

| | |
|---|---|
| Instrument defects found by RUNNING | **11** |
| Green-while-wrong | 5 |
| Red-while-fine | 1 |
| Found by reading the code | **0** |


---

## PHASE 12 · T2 · ENGINE=both — measured, not tuned, 2026-09-08

### ✅ T2.0 · The measurement that changed the fix

Everything below was measured on this machine. The reference Makefile that prompted this
work uses `0.42 / 0.42` for `both`; adopting that number here would have been wrong.

| Quantity | Value | Source |
|---|---|---|
| Card total | 12288 MiB | `nvidia-smi` |
| Desktop resident | ~2300 MiB | measured with no engine running |
| SGLang alone @ 0.55 | ~7260 MiB | 9560 used − 2300 desktop |
| Weights on disk (AWQ INT4) | 5325 MiB (5.2 GiB) | `du` on the HF cache volume |
| This repo's own preflight sizing | 9200 MiB/engine | `5500 × 1.4 + 1500`, `engine_preflight.sh` |

```
  ENGINE=both needs   2 × 9200 = 18400 MiB
  card total                     12288 MiB
  deficit                         6112 MiB     -> 1.5x the entire card
```

Floor estimate, ignoring the desktop entirely: 2×5325 weights + 2 CUDA contexts (~600)
= 11250, leaving 1038 MiB for TWO KV caches — and with the 2300 MiB desktop resident,
13550 > 12288. **`both` cannot fit at any fraction on this card.**

📝 So the fix is NOT a smaller fraction. Picking numbers that still cannot fit would be
the same class of error as a check that reports green without proving anything.

### ⚠️ T2.1 · The real gap: per-mode memory knobs did not exist

`ENGINE_VLLM_FRAC`, `ENGINE_SGLANG_FRAC` and `ENGINE_CTX` were absent entirely — every
mode silently used whatever `.env` happened to say, including `both`.

- ✅ Added for all four modes plus the no-GPU override
- ✅ `vllm` / `sglang` / `none` keep the values `.env` already carries, so their
      behaviour is unchanged
- ✅ Kept as TWO separate knobs on purpose: vLLM's `--gpu-memory-utilization` and
      SGLang's `--mem-fraction-static` are not the same measurement (documented in
      `docker-compose.gpu.yml`), so one shared number would be wrong for one of them

```
  ENGINE=vllm    vllm=0.80 sglang=0.55 ctx=8192 chain=local-vllm,groq,openai
  ENGINE=sglang  vllm=0.80 sglang=0.55 ctx=8192 chain=local-sglang,groq,openai
  ENGINE=both    vllm=0.42 sglang=0.42 ctx=4096 chain=local-vllm,local-sglang,groq,openai
  ENGINE=none    vllm=0.80 sglang=0.55 ctx=8192 chain=groq,openai
  GPU=0 both     vllm=0.80 sglang=0.55 ctx=8192 chain=groq,openai
```

### ⚠️ T2.3 · `both` used to fail SIX MINUTES too late

`ENGINE_START := vllm sglang`, and each engine runs its own single-engine preflight.
`vllm-up` sees ~9900 MiB free ≥ 9200 and **passes**, loads for ~6 minutes, and only then
does `sglang-up` refuse with ~700 MiB free. The failure arrived long after the decision
that caused it, and its message said nothing about `both` never having been possible.

- ✅ A pair-aware check now runs BEFORE anything loads, and refuses with the arithmetic
- ✅ Honours the existing `SKIP_MEM_CHECK=1` rather than inventing a second override
- ✅ Proven, and proven to touch nothing:

```
$ make up-engine ENGINE=both

  REFUSING ENGINE=both: this card cannot hold two engines.

      card total   12288 MiB
      needed      ~18400 MiB   (2 x (5500 weights x1.4 + 1500 runtime))

  Each engine loads its OWN copy of the weights, so this is not a
  fraction to tune - it is more memory than the card has. Lowering
  ENGINE_VLLM_FRAC/ENGINE_SGLANG_FRAC cannot fix it.

  Use one engine:   make up ENGINE=sglang     (or ENGINE=vllm)
  Hosted only:      make up ENGINE=none
  Override anyway:  make up ENGINE=both SKIP_MEM_CHECK=1

sglang before: Up 42 minutes (healthy)
sglang after : Up 42 minutes (healthy)      <- untouched
vllm         : never started
```

Refused in about a second, instead of six minutes and a half-loaded card.

### ⏳ T2.2 · Export verified by INSPECTION, not execution — stated honestly

`up-engine` now exports `VLLM_GPU_MEMORY_UTILIZATION`, `SGLANG_MEM_FRACTION`,
`VLLM_MAX_MODEL_LEN` and `SGLANG_MAX_MODEL_LEN` before calling `<engine>-up`, so shell
env beats `.env` for compose `${VAR}` interpolation — the same mechanism `up-app` uses
for `SERVING_CHAIN`.

This could NOT be proven without restarting the engine (~6 min), and the per-mode values
for `sglang` are identical to `.env`, so a restart would show no difference anyway.
Baseline captured for a future comparison — the currently running container was started
BEFORE this patch, from `.env`:

```
--mem-fraction-static 0.55
--context-length      8192
```

Prove it later with a value `.env` does not carry:

```
make down-engine && make up-engine ENGINE=sglang ENGINE_SGLANG_FRAC=0.50
docker inspect tp-sglang --format '{{join .Config.Cmd " "}}' | tr ' ' '\n' | grep -A1 mem-fraction
```

