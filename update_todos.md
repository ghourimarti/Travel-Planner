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

- ⏳ **R4.1 First vLLM run** — wired, never executed. Contends for the same GPU as SGLang.
- ⏳ **R4.2 GPU node group + scale-to-zero (Terraform)** — cloud spend, never written.
- ⏳ **R4.3 VHDX compact** — reclaims disk to Windows but requires stopping Docker entirely.


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
