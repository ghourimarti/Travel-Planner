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

- ✅ **S1 · Monorepo + `tp_core` foundation**
  - ✅ **S1.1 uv workspace** — `pyproject.toml`, `uv.lock`, five packages + three apps
  - ✅ **S1.2 Typed configuration that fails fast** — `tp_core/settings.py`
  - ✅ S1.2.1 pydantic-settings; a missing required key raises at import, not at first call
  - ✅ S1.2.2 `extra="ignore"` so adding an env var never breaks startup
  - ✅ **S1.3 Structured logging to stdout** — `tp_core/logging.py` (structlog, JSON)
  - ✅ **S1.4 Exception hierarchy** — `tp_core/exceptions.py` (`ConfigError` and friends)
  - ✅ **S1.5 Gate wired and green** — strict mypy + ruff + pytest (6 tests at the time)
  - ✅ **S1.6 Implements D17 (config) and D22 (repo)** — recorded in commit `24a8f3b`

- 🔄 **S2 · External tools layer**
  - ✅ **S2.1 Shared HTTP client with timeouts + retry** — `tp_tools/_http.py`
  - ✅ **S2.2 Geocoding** — `tp_tools/geocode.py` · 3 tests
  - ✅ **S2.3 POI lookup (Overpass / OSM)** — `tp_tools/pois.py` · 6 tests
  - ✅ **S2.4 Routing** — `tp_tools/routing.py` · 2 tests
  - ✅ **S2.5 Weather** — `tp_tools/weather.py` · 1 test
  - ✅ **S2.6 Typed payloads, not dicts** — `tp_tools/models.py`
  - 🔄 **S2.7 Self-hosted Overpass** — `make downv-overpass` kept deliberately separate
  - ⏸️ S2.7.1 OSM import is a 2–4 h job; its volume must never be pruned (see 8.4.8.3)

- 🔄 **S3 · Retrieval / RAG**
  - ✅ **S3.1 Corpus construction** — `tp_retrieval/corpus.py`
  - ✅ **S3.2 Embedder behind an interface** — `tp_retrieval/embedder.py` (D5, hardest to reverse)
  - ✅ **S3.3 Vector store adapter (Qdrant)** — `tp_retrieval/vectorstore.py`
  - ✅ **S3.4 Ingestion pipeline** — `tp_retrieval/ingest.py`, `make ingest`
  - ✅ **S3.5 Retrieval + reranking** — `retrieve.py`, `rerank.py` · 6 tests
  - 🔄 **S3.6 Operational hazard documented** — index and query embedder must match
  - 🔄 S3.6.1 A mismatch degrades RAG **silently**; no automated guard exists yet

- ✅ **S4 · LLM gateway + tiering**
  - ✅ **S4.1 Provider enum + tiers** — `tp_core/llm/types.py` (CHEAP / MID / FRONTIER)
  - ✅ **S4.2 Model catalogue per tier** — `llm/models.py` (`TIER_ROUTING`) · 3 tests
  - ✅ **S4.3 Provider adapters** — `llm/providers.py` (Groq, OpenAI, Anthropic)
  - ✅ **S4.4 Gateway with failover + token/cost capture** — `llm/gateway.py` · 5 tests
  - ✅ **S4.5 Transient vs permanent failure split** — a 4xx is our bug, not the venue's

- ✅ **S5 · Agent graph**
  - ✅ **S5.1 Graph state** — `tp_agents/state.py`
  - ✅ **S5.2 Nodes** — `tp_agents/nodes.py` (retrieve -> ground -> draft)
  - ✅ **S5.3 Prompts as code, versioned** — `tp_agents/prompts.py`
  - ✅ **S5.4 Structured output schemas** — `tp_agents/schemas.py` (`Itinerary`, `TripItinerary`)
  - ✅ **S5.5 Graph assembly** — `tp_agents/graph.py::build_planner_graph` · 10 tests

- ✅ **S6 · Critic + corrective loop**
  - ✅ **S6.1 Critic pass over the drafted itinerary** — `tp_agents/critic.py` · 2 tests
  - ✅ **S6.2 Bounded correction cycles** — a loop that cannot run away
  - ✅ **S6.3 Verified live** — the Kyoto run took **1 critic correction** (see 8.5.4)

- ✅ **S7 · API surface**
  - ✅ **S7.1 FastAPI app** — `apps/api/src/tp_api/main.py`
  - ✅ **S7.2 Plan / run / stream endpoints** — 16 tests in `apps/api/tests/test_api.py`
  - ✅ **S7.3 Container** — `apps/api/Dockerfile`
  - ✅ **S7.4 Health and readiness mean different things**

- ✅ **S8 · Multi-city coordinator**
  - ✅ **S8.1 Coordinator fans out per city, then reconciles** — `tp_agents/coordinator.py`
  - ✅ **S8.2 Per-city worker reuses the single-city graph** — no second implementation
  - ✅ **S8.3 Trip-level schema** — `TripItinerary` · 2 tests

- ✅ **S9 · Async execution — dispatch · checkpointer · SSE**
  - ✅ **S9.1 Celery app + Redis broker** — `tp_core/celery.py` (D11)
  - ✅ **S9.2 Worker app** — `apps/worker/`, `make worker`
  - ✅ **S9.3 Run registry + persistence** — `tp_core/runs.py` (5 tests), `tp_core/db.py`
  - ✅ **S9.4 Graph checkpointer** — `tp_agents/checkpoint.py` · 3 tests
  - ✅ **S9.5 Event bus** — `tp_core/events.py`
  - ✅ **S9.6 SSE streaming to the browser** — `test_stream.py` · 2 tests
  - ✅ **S9.7 Committed** — `ae1fda8`, includes S9c

- ✅ **S10 · Caching + cost controls**
  - ✅ **S10.a Caching + retry** — `tp_core/cache.py` · 4 tests (D10)
  - ✅ **S10.b Cap + kill-switch + budget gate** — `tp_core/control.py` (2), `test_cost.py` (2),
  `test_budget.py` (1)
  - ⏸️ S10.b.1 **Awaiting commit** — code landed, not yet committed

- ✅ **S11 · Observability**
  - ✅ **S11.1 OpenTelemetry tracing** — `tp_core/tracing.py` · 4 tests
  - ✅ **S11.2 Langfuse LLM tracing** — keys live in `.env`
  - ✅ **S11.3 Prometheus metrics** — `tp_core/metrics.py` · 4 tests
  - ✅ **S11.4 Prometheus + Grafana + Loki/Promtail** — `infra/observability/`
  - ✅ S11.4.1 `prometheus.yml` · `promtail.yml` · `grafana-datasources.yml`
  - ✅ S11.4.2 Dashboard — `infra/observability/dashboards/voyantra.json`
  - ✅ **S11.5 Alerting** — `alerts.yaml` + `alertmanager.yml`
  - ✅ **S11.6 Compose stack** — `docker-compose.observability.yml`, `make observability`

  - ✅ **S11.1 · Grafana rebuild — instrument first, then chart** *(was PHASE 9 · T3)* — [detail →](docs/execution-log.md#s111-grafana-rebuild-instrument-first-then-chart-was-phase-9-t3)
  - ✅ **T3 · Grafana — instrument first, then chart** — [detail →](docs/execution-log.md#t3-grafana-instrument-first-then-chart)
  - ✅ **T3 · RESULT — verified 2026-09-07** — [detail →](docs/execution-log.md#t3-result-verified-2026-09-07)
    - ⏳ **T3.O1 A stray dashboard exists** — `uid=dfxi63ldmhla8b`, title "Voyantra", no folder.
- ✅ **S12 · Security + Auth0**
  - ✅ **S12.1 JWT verification** — `tp_core/auth.py` · 5 tests (D9)
  - ✅ **S12.2 ACL enforced at retrieval, not after** — `tp_core/guard.py` · 4 tests
  - ✅ **S12.3 PII redaction on the logging path**
  - ✅ **S12.4 Prompt-injection suite** — `packages/agents/tests/test_injection.py` · 3 tests
  - ✅ **S12.5 Rate limiting** — `tp_core/ratelimit.py` · 4 tests
  - ✅ **S12.6 Supply-chain gates** — `make audit-deps` · `sast` · `secrets` · `licenses` · `audit`

- ✅ **S13 · Next.js frontend (Streamlit retired)**
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


## PHASE 5 — Local inference venue + repo ergonomics *(was PHASE 8; now also absorbs PHASE 9 · T1/T2 and PHASE 12 · T0/T1/T2)*

- ✅ **5.1 · Makefile restructure**
  - ✅ **5.1.1 Boxed section titles, then a documentation block, then the commands**
  - ✅ **5.1.2 Every variable declared once, in a single section at the top**
  - ✅ **5.1.3 Grew 196 -> 616 lines, 35 -> 58 targets, 13 boxed sections**
  - ✅ **5.1.4 Engine / GPU-profile resolution block**
  - ✅ 5.1.4.1 `ENGINE=vllm|sglang|none` maps to profile + chain + what to stop
  - ✅ 5.1.4.2 An unknown value `$(error ...)`s instead of running the wrong thing
  - ✅ **5.1.5 Independent `vllm-*` family** — `vllm-up` · `-down` · `-upv` · `-downv` · `-test`
  - ✅ **5.1.6 Independent `sglang-*` family** — the same five, touching only SGLang
  - ✅ **5.1.7 One-command full bring-up** — `make up-vllm` / `make up-sglang`
  - ✅ 5.1.7.1 image (pull if absent) -> container -> weights -> load -> **serve**
  - 📝 5.1.7.2 I claimed `up-with-engine` exporting `SERVING_CHAIN` made `ENGINE=`
  authoritative. **It had no consumer** — `docker-compose.app.yml` uses an explicit
  `environment:` allowlist, not `env_file`, so the var reached no container.
  - ✅ 5.1.7.3 **FIXED** — `ENGINE_URL_ENV` added per branch; the target now exports the
  engine URL alongside the chain, and `app.yml` names both under `environment:`
  - ⚠️ 5.1.7.4 **Ordering bug found and fixed** — the app was started BEFORE the engine,
  so its opening requests failed the local leg, tripped the breaker and were
  answered (and billed) by a hosted venue. Engine now comes up first.
  - ✅ **5.1.8 Support targets** — `which-engine` · `engine-guide` · `webui` · `clean-models`
  - ✅ **5.1.9 Benchmarks** — `bench-engine` · `bench-groq` · `bench-openai`
  - ⚠️ **5.1.10 `.PHONY` kept on a single line** — the Bash tool mangles line continuations
  - ✅ **5.1.11 Default engine is SGLang**
  - 📝 **5.1.12 False "orphan targets" alarm was mine** — my checker's regex excluded `=`,
  and help strings contain `SERVING_CHAIN=...`. The instrument was wrong, not the system.

- ✅ **5.2 · `.env` / `.env.example` restructure**
  - ✅ **5.2.1 Confirmed a prior session had already restructured both** — 76 vars, 57 sections
  - 📝 5.2.1.1 A stale `Read` showed 239 lines / 74 vars / 26 trailing comments; disk had 490
  lines. One command from overwriting prior work. **Rule adopted: verify with bash.**
  - ✅ **5.2.2 Added a `LOCAL INFERENCE` section** — engine, URLs, models, chains, breaker
  - ✅ **5.2.3 Added inference-tier ports** — vLLM 3019 · SGLang 3020 · WebUI 3021
  - ✅ **5.2.4 Both files now 92 vars, zero drift between them**
  - ✅ **5.2.5 Zero trailing comments** — `VAR=x  # note` parses the comment into the value
  - ✅ **5.2.6 Real secrets preserved byte-exactly and never sent anywhere**
  - ✅ **5.2.7 `SERVING_CHAIN` ships EMPTY** — legacy routing until you opt in

- ✅ **5.3 · Serving chain + circuit breaker**
  - ✅ **5.3.1 Chain grammar + parser** — `tp_core/llm/venues.py`
  - ✅ 5.3.1.1 `local` · `local-vllm` · `local-sglang` · `groq` · `openai` · `anthropic`
  - ✅ 5.3.1.2 `venue:model` overrides the model for that call-point
  - ✅ 5.3.1.3 A bare `sglang` is **rejected at startup**, and the error names the fix
  - ✅ 5.3.1.4 Duplicate venue, unknown venue and empty chain each raise `ConfigError`
  - ✅ 5.3.1.5 A list, not priority numbers — numbers split identity from order
  - ✅ **5.3.2 Two-level configuration (D24 as amended)**
  - ✅ 5.3.2.1 `SERVING_CHAIN` — one baseline order for every tier
  - ✅ 5.3.2.2 `CHAIN_CHEAP` / `CHAIN_MID` / `CHAIN_FRONTIER` override per tier
  - ✅ 5.3.2.3 `raw_chain_for_tier()` — narrow beats broad; empty means "unset", not "empty"
  - ✅ 5.3.2.4 Default leaves FRONTIER hosted — one loaded 7B cannot be three tiers
  - 📝 5.3.2.5 I first built a single chain against an approved per-tier design, because I
  coded before re-reading D24. Resolved as the hybrid above, at your call.
  - ✅ **5.3.3 Circuit breaker** — `tp_core/llm/circuit.py`
  - ✅ 5.3.3.1 CLOSED / OPEN / HALF_OPEN; threshold 3, cooldown 30 s
  - ✅ 5.3.3.2 HALF_OPEN admits **exactly one** probe
  - ✅ 5.3.3.3 A 4xx does not count against a venue
  - ✅ 5.3.3.4 `snapshot()` reports every known leg, not only the one that moved
  - ⚠️ 5.3.3.5 **Clock bug found and fixed** — `snapshot()` mixed an injected clock with
  `time.monotonic()`, so a just-opened leg read half-open. Caught by a new test.
  - ✅ 5.3.3.6 Scope recorded as per-process, with the Redis trade-off written down
  - ✅ **5.3.4 Local provider** — `LocalEngineProvider` in `llm/providers.py`
  - ✅ 5.3.4.1 `AsyncOpenAI(base_url=...)` — one adapter serves both engines
  - ✅ 5.3.4.2 `max_retries=0` — the chain retries, not the client
  - ✅ 5.3.4.3 `cost_usd=0.0` set explicitly (0.0 is a measurement, not a blank)
  - ✅ **5.3.5 Gateway rework** — `llm/gateway.py`
  - ✅ 5.3.5.1 `chains: dict[Tier, list[ChainLeg]]` + `_resolve_chain(tier)`
  - ✅ 5.3.5.2 Precedence: per-tier -> baseline -> legacy `TIER_ROUTING`
  - ✅ 5.3.5.3 Breaker consulted before each leg; a leg with no key is skipped
  **with a warning naming it** — never a silent downgrade
  - ✅ 5.3.5.4 **Backward compatible by construction** — an empty chain reproduces
  legacy routing exactly
  - ✅ **5.3.6 Settings** — `serving_chain` · `serving_engine` · per-tier chains · URLs ·
  models · `circuit_failure_threshold` · `circuit_cooldown_seconds`
  - ✅ **5.3.7 Tests** — `packages/core/tests/test_llm_local_venues.py`, 21 test functions
  - ✅ 5.3.7.1 Includes a test pinning that a 7B never reaches FRONTIER

- 🔄 **5.4 · GPU venue infrastructure**
  - ⚠️ **5.4.0 The extension was never wired to any container** — found by verification,
  not by a test. `docker-compose.app.yml` passes an explicit `environment:` allowlist;
  none of `SERVING_*`, `CHAIN_*`, `VLLM_URL`, `SGLANG_URL`, `CIRCUIT_*` was in it.
  - ✅ 5.4.0.1 Proven inside both containers — every one of them read empty
  - 📝 5.4.0.2 This is why the app kept working: an empty chain falls back to legacy
  `TIER_ROUTING`, so the invalid `SERVING_CHAIN=sglang,...` in `.env` never reached
  a container and never raised. **Luck, not design.**
  - ✅ 5.4.0.3 **FIXED** — 14 vars added to `environment:` on api **and** worker;
  `compose config` validates; ruff clean and 150 passed afterwards
  - ✅ **5.4.1 `docker-compose.gpu.yml`**
  - ✅ 5.4.1.1 vLLM :3019 (`gpu-vllm`) · SGLang :3020 (`gpu-sglang`) · WebUI :3021 (`webui`)
  - ✅ 5.4.1.2 Shared `tp_hf_cache` volume — one 5.5 GB download serves either engine
  - ✅ 5.4.1.3 `shm_size: 8gb`, `ipc: host`
  - ✅ 5.4.1.4 Healthcheck polls the engine's own `/health`, `start_period: 900s`
  — `--wait` alone returns while 5.5 GB of weights are still loading
  - ✅ **5.4.2 Preflight** — `scripts/engine_preflight.sh` · **run, works**
  - ✅ 5.4.2.1 Sizes need as `weights x1.4 + 1.5 GB`; refuses in ~2 s rather than exit 137
  after twenty minutes
  - ✅ 5.4.2.2 Names the container holding the card and prints the command to stop it
  - ✅ **5.4.3 Failure diagnostic** — `scripts/engine_failed.sh`
  - ✅ 5.4.3.1 Branches on **real** container state: running / 137 / crash / gone
  - ✅ 5.4.3.2 Refuses to guess — the obvious "it is still loading" version misleads
  exactly when it matters
  - ✅ **5.4.4 Benchmark harness** — `scripts/bench_venue.py` · **RUN, 5/5 succeeded**
  - ✅ 5.4.4.1 TTFT p50 **50 ms** / p95 559 ms · TPOT p50 **15.2 ms** · **60.8 tok/s**
  - ✅ 5.4.4.2 Warmup discard justified by the data: warmup TTFT 246 ms, run-1 559 ms,
  then ~50 ms steady — the cold request is a different machine
  - ⚠️ 5.4.4.3 `make bench-groq` **fails 404** — see 8.8
  - ✅ **5.4.5 Hardware recon** — RTX 3060 12 GB, cc 8.6; passthrough verified inside a container
  - ✅ **5.4.6 Model chosen** — `Qwen/Qwen2.5-7B-Instruct-AWQ`, INT4, ~5.5 GB, ungated
  - ✅ **5.4.7 Both engine images confirmed already pulled** — vLLM 30.8 GB, SGLang 47 GB
  - ✅ **5.4.8 Disk reclaim, reviewed line by line before deleting**
  - ✅ 5.4.8.1 Docker internals + odds (1.13 GB) · stale p61 tags (1.80 GB) · dupes (8.14 GB)
  - ⚠️ 5.4.8.2 Prevented deletion of the 30.8 GB vLLM image that read as "unused"
  - ⚠️ 5.4.8.3 Prevented `docker volume prune` — **547 of 565** volumes read as dangling,
  including the 2–4 h OSM import, because `compose down` removes containers
  - 📝 5.4.8.4 I first claimed ~11 GB reclaimed; actual was **6.8 GB** — `docker images`
  counts shared base layers once per image
  - ⏳ 5.4.8.5 VHDX compact, to hand the space back to Windows — not done

- ✅ **5.5 · Venue on the response contract + metrics**
  - ✅ **5.5.1 Metrics** — `tp_core/metrics.py`
  - ✅ 5.5.1.1 `LLM_TOKENS` · `LLM_COST` counters
  - ✅ 5.5.1.2 `CIRCUIT_STATE` gauge, `multiprocess_mode="mostrecent"`
  - ✅ 5.5.1.3 Labels bounded to enum values — no unbounded cardinality
  - ✅ 5.5.1.4 `record_venue_usage()` + `record_circuit()`
  - ✅ **5.5.2 `venues` added to the schemas** — `Itinerary` and `TripItinerary`
  - ✅ **5.5.3 Accumulated along the whole path**
  - ✅ 5.5.3.1 `nodes.py` — union of this response's venue with the prior set
  - ✅ 5.5.3.2 `critic.py` — the critic's own venue merged in
  - ✅ 5.5.3.3 `coordinator.py` — union across every city
  - ✅ 5.5.3.4 Rides the existing `result` JSON column — **no DB migration**
  - ✅ **5.5.4 Proven end-to-end on a real run**
  - ✅ 5.5.4.1 Kyoto, 1 day, 5 POIs, $0.00656, 1 critic correction
  - ✅ 5.5.4.2 `venues: ['openai']` survives `model_dump(mode="json")`

- ✅ **5.6 · Documentation**
  - ✅ **5.6.1 `docs/DECISION_LOG_LOCAL_INFERENCE.md`** — 299 -> 441 lines, dated amendments
  - ✅ 5.6.1.1 D24 recorded as the **hybrid actually built**, not as first drafted
  - ✅ 5.6.1.2 An explicit verified-vs-unverified table
  - ✅ **5.6.2 `docs/gpu-venue.md`** — the bring-up runbook
  - ✅ 5.6.2.1 "A liveness check is not a capacity check"
  - ✅ 5.6.2.2 "Declared is not working"
  - ✅ 5.6.2.3 vLLM `--gpu-memory-utilization` (fraction of **free**) vs SGLang
  `--mem-fraction-static` (fraction of **total**) — not the same knob
  - ✅ 5.6.2.4 One engine at a time: 0.80 + 0.70 is 150% of the card, and it **wedges**
  at "Starting to load model" rather than failing fast
  - ✅ 5.6.2.5 Never `docker volume prune`
  - ✅ 5.6.2.6 The first download must not be interrupted — `huggingface_hub` does not resume
  - ✅ 5.6.2.7 `make webui` is deliberately the unguarded path, so engine quality and
  product quality are judged separately
  - ✅ **5.6.3 `docs/DECISION_LOG.md` left untouched** — verified

- ✅ **5.7 · Bring-up and measurement**
  - ✅ **5.7.1 Engine STARTED and PROVEN GENERATING** — healthy in 360 s; `/v1/chat/completions`
  returned real text; `max_total_num_tokens=11881`, 10406 MiB used / 1708 MiB free.
  Original blocker note follows:
  - ✅ **5.7.1-orig Start an engine and prove it generates** — **UNBLOCKED**:
  `p5-medical-chatbot-sglang-1` exited 30 h ago; the card is free. Engine started and
  is loading; not yet proven to generate.
  - ✅ 5.7.1.1 Preflight **correctly refused** — 8980 MiB free vs a 9200 MiB heuristic.
  The check did its job; it was not bypassed blindly.
  - ✅ 5.7.1.2 `SGLANG_MEM_FRACTION` 0.70 -> **0.55** to leave ~1.4 GB desktop headroom,
  because the 3055 MiB in use is ordinary Windows desktop, not a stale container
  - ⚠️ 5.7.1.3 SGLang additionally reserves **1024 MiB for CUDA IPC**, which the
  preflight heuristic does not model — first number to lower if it OOMs
  - ✅ **5.7.2 `make bench-engine` ran** — TTFT p50 50 ms · TPOT p50 15.2 ms · 60.8 tok/s
  - ✅ **5.7.3 Chain flipped and confirmed** — `venues: ['local-sglang']` at $0.00 on a real plan
  - ✅ **5.7.4 `scripts/ensure_weights.sh`** — WRITTEN and RUNNING, prompted by a real failure
  - ⚠️ 5.7.4.1 First cold start **stalled**: 0.87 GB of 5.5 GB, then **zero bytes for 6
  minutes** while the container sat `unhealthy` and kept holding the GPU.
  Unauthenticated HF downloads are rate-limited and hang without erroring.
  - ✅ 5.7.4.2 Weights now fetched in a throwaway container with **no `--gpus`** — a
  stalled download must not park the card
  - ✅ 5.7.4.3 Stall detection by sampling cache growth; a zero-growth window is treated
  as death and retried. Safe because `.incomplete` blobs resume.
  - ✅ 5.7.4.4 Completion verified by **content** (`*.safetensors` present), not exit status
  - ⚠️ 5.7.4.5 **`start_period: 900s` is too short** — it covers a cold *load*, not a cold
  *download* on a rate-limited link. `make sglang-up`'s `--wait-timeout 900` would
  have declared failure on a download that was still alive. Not yet fixed.
  ---

- ✅ **5.8 · PROVEN END-TO-END *(2026-09-07)*** — [detail →](docs/execution-log.md#58-proven-end-to-end-2026-09-07)
  - ⏳ 5.8.3.4 **NOT FIXED** — choosing a replacement model is a D4 decision (quality
- ✅ **5.9 · EVAL GATE AGAINST THE LOCAL ENGINE *(2026-09-07)*** — [detail →](docs/execution-log.md#59-eval-gate-against-the-local-engine-2026-09-07)
  - ⏳ 5.9.5.2 **NOT FIXED** — either widen the golden set or state the intent
- ✅ **5.10 · FAILOVER CHAIN PROVEN END-TO-END *(2026-09-07)*** — [detail →](docs/execution-log.md#510-failover-chain-proven-end-to-end-2026-09-07)
  - ⚠️ **8.10.5 The Groq rung had to be repaired first — it could not have worked** — [detail →](docs/execution-log.md#8105-the-groq-rung-had-to-be-repaired-first-it-could-not-have-worked)
    - ⏳ 5.10.5.5 Verify the price against Groq's pricing page — estimate, not fact
- ✅ **5.11 · Makefile composition · .env completion** *(was PHASE 9; its Grafana/T3 part is now Phase 4 · S11.1)* — [detail →](docs/execution-log.md#511-makefile-composition-env-completion-was-phase-9-its-grafanat3-part-is-now-phase-4-s111)
- ✅ **5.12 · T1 · Makefile — compose aggregates from primitives** *(was PHASE 9 · T1)* — [detail →](docs/execution-log.md#512-t1-makefile-compose-aggregates-from-primitives-was-phase-9-t1)
- ✅ **5.13 · T2 · .env — audit, then wire what is real** *(was PHASE 9 · T2)* — [detail →](docs/execution-log.md#513-t2-env-audit-then-wire-what-is-real-was-phase-9-t2)
- ✅ **5.14 · Gate after every task** *(was PHASE 9)* — [detail →](docs/execution-log.md#514-gate-after-every-task-was-phase-9)
- ✅ **5.12 · T1 · RESULT — verified 2026-09-07** *(was PHASE 9 · T1)* — [detail →](docs/execution-log.md#512-t1-result-verified-2026-09-07-was-phase-9-t1)
- ✅ **5.13 · T2 · DETAILED PLAN — audited against the code, 2026-09-07** *(was PHASE 9 · T2)* — [detail →](docs/execution-log.md#513-t2-detailed-plan-audited-against-the-code-2026-09-07-was-phase-9-t2)
  - ✅ **T2.A · Audit result — what the code actually does today** — [detail →](docs/execution-log.md#t2a-audit-result-what-the-code-actually-does-today)
  - ✅ **T2.B · Implementation, in dependency order** — [detail →](docs/execution-log.md#t2b-implementation-in-dependency-order)
- ✅ **5.13 · T2 · RESULT — verified 2026-09-07** *(was PHASE 9 · T2)* — [detail →](docs/execution-log.md#513-t2-result-verified-2026-09-07-was-phase-9-t2)
  - ✅ **The live proof** — [detail →](docs/execution-log.md#the-live-proof)
  - ✅ **Defects this task surfaced** — [detail →](docs/execution-log.md#defects-this-task-surfaced)
  - ✅ **Still open** — [detail →](docs/execution-log.md#still-open)
    - 🔄 **T2.O1 The Postgres breaker is settings-only.** `runs.py` has no degrade path, so
    - ⏳ **T2.O2 `SERVING_CHAIN` still disagrees with the Makefile.** `.env` says
- ✅ **5.15 · T0 · Additive Makefile targets, 2026-09-08** *(was PHASE 12 · T0)* — [detail →](docs/execution-log.md#515-t0-additive-makefile-targets-2026-09-08-was-phase-12-t0)
  - ⚠️ **T0.0 · A defect I introduced and caught in the same session** — [detail →](docs/execution-log.md#t00-a-defect-i-introduced-and-caught-in-the-same-session)
  - ✅ **Status of all 21 targets** — [detail →](docs/execution-log.md#status-of-all-21-targets)
  - ✅ **Two deliberate departures from the supplied reference** — [detail →](docs/execution-log.md#two-deliberate-departures-from-the-supplied-reference)
  - 📌 **Stack state observed during this work** — [detail →](docs/execution-log.md#stack-state-observed-during-this-work)
- ✅ **5.16 · Four safety guards on existing targets, 2026-09-08** *(was PHASE 12 · T1)* — [detail →](docs/execution-log.md#516-four-safety-guards-on-existing-targets-2026-09-08-was-phase-12-t1)
  - ✅ **T1.4 · GPU auto-detect — a chain must not NAME a venue that cannot answer** — [detail →](docs/execution-log.md#t14-gpu-auto-detect-a-chain-must-not-name-a-venue-that-cannot-answer)
  - ✅ **T1.1 · `up-app` validates SERVING_CHAIN with the REAL parser** — [detail →](docs/execution-log.md#t11-up-app-validates-serving_chain-with-the-real-parser)
  - ✅ **T1.2 · `up-app` reports the corpus — and WARNS rather than refuses** — [detail →](docs/execution-log.md#t12-up-app-reports-the-corpus-and-warns-rather-than-refuses)
  - ⚠️ **T1.3 · Prometheus reload — the guard would have been a NO-OP as designed** — [detail →](docs/execution-log.md#t13-prometheus-reload-the-guard-would-have-been-a-no-op-as-designed)
  - ✅ **T0 items closed now that the stack is up** — [detail →](docs/execution-log.md#t0-items-closed-now-that-the-stack-is-up)
- ✅ **5.17 · T0 completion + defects #8-#11, 2026-09-08** *(was PHASE 12 · T0 completion)* — [detail →](docs/execution-log.md#517-t0-completion-defects-8-11-2026-09-08-was-phase-12-t0-completion)
  - ⚠️ **Defect #8 · The drill would have BLAMED THE APP for its own broken environment** — [detail →](docs/execution-log.md#defect-8-the-drill-would-have-blamed-the-app-for-its-own-broken-environment)
  - ⚠️ **Defect #9 · The ENGINE was not part of the lifecycle (reported by the user)** — [detail →](docs/execution-log.md#defect-9-the-engine-was-not-part-of-the-lifecycle-reported-by-the-user)
  - ⚠️ **Defect #10 · A message that was true and useless** — [detail →](docs/execution-log.md#defect-10-a-message-that-was-true-and-useless)
  - ⚠️ **Defect #11 · `make inspect` was ALWAYS red** — [detail →](docs/execution-log.md#defect-11-make-inspect-was-always-red)
  - ✅ **T0.2b · `make inspect` — final, on a stable stack** — [detail →](docs/execution-log.md#t02b-make-inspect-final-on-a-stable-stack)
  - ✅ **Running tally** — [detail →](docs/execution-log.md#running-tally)
- ✅ **5.18 · ENGINE=both — measured, not tuned, 2026-09-08** *(was PHASE 12 · T2)* — [detail →](docs/execution-log.md#518-engineboth-measured-not-tuned-2026-09-08-was-phase-12-t2)
  - ✅ **T2.0 · The measurement that changed the fix** — [detail →](docs/execution-log.md#t20-the-measurement-that-changed-the-fix)
  - ⚠️ **T2.1 · The real gap: per-mode memory knobs did not exist** — [detail →](docs/execution-log.md#t21-the-real-gap-per-mode-memory-knobs-did-not-exist)
  - ⚠️ **T2.3 · `both` used to fail SIX MINUTES too late** — [detail →](docs/execution-log.md#t23-both-used-to-fail-six-minutes-too-late)
  - ⏳ **T2.2 · Export verified by INSPECTION, not execution — stated honestly** — [detail →](docs/execution-log.md#t22-export-verified-by-inspection-not-execution-stated-honestly)

## PHASE 6 — Production hardening *(was PHASE 5; now absorbs PHASE 10, PHASE 11 and PHASE 13)*

- ✅ **6.1 Chaos tests** — `packages/agents/tests/test_chaos.py` · 3 tests
- ✅ **6.2 Backup + restore drill** — `scripts/backup_restore_drill.sh`
- ✅ **6.3 Load test path** — `make load`
- ✅ **6.4 Evaluation harness** — `packages/eval/`
  - ✅ 6.4.1 Golden set — `tp_eval/golden.py`
  - ✅ 6.4.2 Runner + CLI — `runner.py`, `cli.py`, `__main__.py`
  - ✅ 6.4.3 Metrics + LLM judge — `metrics.py`, `judge.py`, `ragas_judge.py`
  - ✅ 6.4.4 CI gate — `tp_eval/gate.py` · 6 tests
  - ✅ 6.4.5 Baseline recorded — `packages/eval/baselines/baseline-rag.json`
- ✅ **6.5 Degradation behaviour proven** — a partial itinerary rather than a 500

- ✅ **6.6 · Clearing the backlog, ordered by BLAST RADIUS** *(was PHASE 10)* — [detail →](docs/execution-log.md#66-clearing-the-backlog-ordered-by-blast-radius-was-phase-10)
- ✅ **TIER 0 — NO RISK · read-only or measurement, nothing changes** — [detail →](docs/execution-log.md#tier-0-no-risk-read-only-or-measurement-nothing-changes)
- ✅ **TIER 1 — VERY LOW RISK · config, reversible, app behaviour unchanged** — [detail →](docs/execution-log.md#tier-1-very-low-risk-config-reversible-app-behaviour-unchanged)
- ✅ **TIER 2 — LOW RISK · additive code, covered by tests** — [detail →](docs/execution-log.md#tier-2-low-risk-additive-code-covered-by-tests)
- ✅ **TIER 3 — YOURS TO DECIDE · not mine to choose** — [detail →](docs/execution-log.md#tier-3-yours-to-decide-not-mine-to-choose)
- ✅ **TIER 4 — HIGHER RISK / LARGER · deliberately last** — [detail →](docs/execution-log.md#tier-4-higher-risk-larger-deliberately-last)
  - 🔄 **R4.2 GPU node group + scale-to-zero (Terraform)** — WRITTEN + VALIDATED, never planned.
  - ⏸️ **R4.3 VHDX compact** — deferred by choice; builder prune done instead.
- ✅ **TIER 0 · RESULT — 2026-09-07 · all four done, nothing broken** — [detail →](docs/execution-log.md#tier-0-result-2026-09-07-all-four-done-nothing-broken)
- ✅ **TIER 1 · RESULT — 2026-09-07** — [detail →](docs/execution-log.md#tier-1-result-2026-09-07)
- ✅ **TIER 2 · RESULT — 2026-09-07** — [detail →](docs/execution-log.md#tier-2-result-2026-09-07)
  - ✅ **R2.1 · Embedder-mismatch guard** — [detail →](docs/execution-log.md#r21-embedder-mismatch-guard)
  - ✅ **R2.2 · Postgres breaker wired at `session_scope()`** — [detail →](docs/execution-log.md#r22-postgres-breaker-wired-at-session_scope)
  - ✅ **Incidental confirmation** — [detail →](docs/execution-log.md#incidental-confirmation)
- ✅ **TIER 3 · RESULT — 2026-09-07 · decided and executed** — [detail →](docs/execution-log.md#tier-3-result-2026-09-07-decided-and-executed)
  - 📝 **R3.1 · Chain — DECIDED TWICE, because my first analysis was wrong** — [detail →](docs/execution-log.md#r31-chain-decided-twice-because-my-first-analysis-was-wrong)
  - ✅ **R3.3 · Eval gate widened — and a side effect caught before it shipped** — [detail →](docs/execution-log.md#r33-eval-gate-widened-and-a-side-effect-caught-before-it-shipped)
    - 🔄 R3.3.5 **The RAG gate still has the granularity problem**, now honestly located: it
- ✅ **TIER 4 · R4.1 RESULT — vLLM's first ever run, 2026-09-07** — [detail →](docs/execution-log.md#tier-4-r41-result-vllms-first-ever-run-2026-09-07)
  - ⚠️ **R4.1.8 vLLM BEATS SGLang on every measured axis** — [detail →](docs/execution-log.md#r418-vllm-beats-sglang-on-every-measured-axis)
    - ⏳ R4.1.8c **The default engine is still SGLang and I have NOT changed it.** vLLM is
- ✅ **TIER 4 · RESULT — 2026-09-07** — [detail →](docs/execution-log.md#tier-4-result-2026-09-07)
  - ✅ **R4.3-alt · Disk: builder prune only, by your choice** — [detail →](docs/execution-log.md#r43-alt-disk-builder-prune-only-by-your-choice)
    - ⏸️ R4.3.4 **VHDX compact deferred.** `docker_data.vhdx` is **367 GB** on disk against
  - 🔄 **R4.2 · GPU node group — written, validated, NOT planned** — [detail →](docs/execution-log.md#r42-gpu-node-group-written-validated-not-planned)
    - ⏳ R4.2.3 **NEVER PLANNED — this is the honest status.** validate proves syntax and
    - ⏳ R4.2.4 **Deliberately NOT merged into `module.eks`.** The merge is one line, but it
    - ⏳ R4.2.5 The Helm chart has no matching toleration/nodeSelector, so a GPU node would
  - 📌 **WHEN CREDENTIALS EXIST — resume here** — [detail →](docs/execution-log.md#when-credentials-exist-resume-here)
- ✅ **6.7 · Brutal inspection: 2 documents + 2 single-command scripts** *(was PHASE 11)* — [detail →](docs/execution-log.md#67-brutal-inspection-2-documents-2-single-command-scripts-was-phase-11)
- ✅ **S · SURVEY RESULT — what the app actually is** — [detail →](docs/execution-log.md#s-survey-result-what-the-app-actually-is)
- ✅ **A · FIX FIRST (documentation must not certify a lie)** — [detail →](docs/execution-log.md#a-fix-first-documentation-must-not-certify-a-lie)
- ✅ **B · `docs/INSPECTION.md` — the working battery** — [detail →](docs/execution-log.md#b-docsinspectionmd-the-working-battery)
- ✅ **C · `docs/INSPECTION_DEEP.md` — the full manual** — [detail →](docs/execution-log.md#c-docsinspection_deepmd-the-full-manual)
- ✅ **D · The two scripts** — [detail →](docs/execution-log.md#d-the-two-scripts)
- ✅ **E · Cache clearing** — [detail →](docs/execution-log.md#e-cache-clearing)
- ✅ **Quality bar for every claim** — [detail →](docs/execution-log.md#quality-bar-for-every-claim)
  - ⏳ No `✅` without a command whose output is quoted. Unverified stays `⏳`.
  - ⏳ Every metric and panel cross-checked against `metrics.py` and the dashboard JSON before
- ✅ **6.7.A · RESULT — the spend breaker is now alive, 2026-09-07** *(was PHASE 11 · A)* — [detail →](docs/execution-log.md#67a-result-the-spend-breaker-is-now-alive-2026-09-07-was-phase-11-a)
- ✅ **6.7.B · RESULT — `docs/INSPECTION.md`, 454 lines, 2026-09-07** *(was PHASE 11 · B)* — [detail →](docs/execution-log.md#67b-result-docsinspectionmd-454-lines-2026-09-07-was-phase-11-b)
  - ✅ **Real shapes captured for the document (not estimated)** — [detail →](docs/execution-log.md#real-shapes-captured-for-the-document-not-estimated)
- ✅ **6.7.C · RESULT — `docs/INSPECTION_DEEP.md`, 563 lines, 2026-09-08** *(was PHASE 11 · C)* — [detail →](docs/execution-log.md#67c-result-docsinspection_deepmd-563-lines-2026-09-08-was-phase-11-c)
- ✅ **6.7.C-D · RESULT — completed in a parallel session, verified here 2026-09-08** *(was PHASE 11 · C & D)* — [detail →](docs/execution-log.md#67c-d-result-completed-in-a-parallel-session-verified-here-2026-09-08-was-phase-11-c-d)
  - ✅ **C · `docs/INSPECTION_DEEP.md` — 563 lines, all six parts present** — [detail →](docs/execution-log.md#c-docsinspection_deepmd-563-lines-all-six-parts-present)
  - ✅ **D · Two scripts — 665-line shared module, two 18-line entrypoints** — [detail →](docs/execution-log.md#d-two-scripts-665-line-shared-module-two-18-line-entrypoints)
- ✅ **6.7.D · EXECUTION RESULT — the scripts were RUN, 2026-09-08** *(was PHASE 11 · D)* — [detail →](docs/execution-log.md#67d-execution-result-the-scripts-were-run-2026-09-08-was-phase-11-d)
  - ✅ **D10 · First end-to-end execution — `PASS=56 · FAIL=1`** — [detail →](docs/execution-log.md#d10-first-end-to-end-execution-pass56-fail1)
  - ⚠️ **D11 · Three defects in my own instrument, found by running it** — [detail →](docs/execution-log.md#d11-three-defects-in-my-own-instrument-found-by-running-it)
  - ✅ **D12 · Fixed and PROVEN against the state the old code could not clean** — [detail →](docs/execution-log.md#d12-fixed-and-proven-against-the-state-the-old-code-could-not-clean)
  - ✅ **D13 · Re-run — `EXIT=0 · PASS=57 · FAIL=0`** — [detail →](docs/execution-log.md#d13-re-run-exit0-pass57-fail0)
  - ⚠️ **D14 · `inspect_stack_vllm.py` — ran, and exposed two more instrument defects** — [detail →](docs/execution-log.md#d14-inspect_stack_vllmpy-ran-and-exposed-two-more-instrument-defects)
  - ⏳ **D15 · The vLLM LADDER has still never been exercised — honestly pending** — [detail →](docs/execution-log.md#d15-the-vllm-ladder-has-still-never-been-exercised-honestly-pending)
  - 📌 **D16 · Unattributed, stated as fact only** — [detail →](docs/execution-log.md#d16-unattributed-stated-as-fact-only)
- ✅ **6.7.E · RESULT — cache clearing, RUN not just written, 2026-09-08** *(was PHASE 11 · E)* — [detail →](docs/execution-log.md#67e-result-cache-clearing-run-not-just-written-2026-09-08-was-phase-11-e)
  - ✅ **E1 · `cache-prefix` / `cache-ls` / `cache-clear` on the REAL key shape** — [detail →](docs/execution-log.md#e1-cache-prefix-cache-ls-cache-clear-on-the-real-key-shape)
  - ✅ **E1.1 · Proven SURGICAL — it clears cache and nothing else** — [detail →](docs/execution-log.md#e11-proven-surgical-it-clears-cache-and-nothing-else)
  - ✅ **BEFORE                          ### AFTER** — [detail →](docs/execution-log.md#before-after)
  - ✅ **E1.2 · Proven to make a repeated query genuinely FRESH — the actual requirement** — [detail →](docs/execution-log.md#e12-proven-to-make-a-repeated-query-genuinely-fresh-the-actual-requirement)
  - ⚠️ **E2 · GAP FOUND — `runs-clear` orphaned the LangGraph checkpoint tables** — [detail →](docs/execution-log.md#e2-gap-found-runs-clear-orphaned-the-langgraph-checkpoint-tables)
  - ✅ **E2.1 · New `make state-ls` — see it before you delete it** — [detail →](docs/execution-log.md#e21-new-make-state-ls-see-it-before-you-delete-it)
  - ✅ **E2.2 · `make metrics-note` — the honest limit, verified** — [detail →](docs/execution-log.md#e22-make-metrics-note-the-honest-limit-verified)
  - ✅ **E3 · The caching FEATURE was not removed — only commands added** — [detail →](docs/execution-log.md#e3-the-caching-feature-was-not-removed-only-commands-added)
  - ✅ **E4 · Application verified unharmed after every change in this phase** — [detail →](docs/execution-log.md#e4-application-verified-unharmed-after-every-change-in-this-phase)
- ✅ **6.7.E · RESULT — cache clearing, 2026-09-08** *(was PHASE 11 · E)* — [detail →](docs/execution-log.md#67e-result-cache-clearing-2026-09-08-was-phase-11-e)
  - ⚠️ **E.5 A stray `scratchpad/` was left in the project root by the parallel session** — [detail →](docs/execution-log.md#e5-a-stray-scratchpad-was-left-in-the-project-root-by-the-parallel-session)
- ✅ **6.7.D15 · RESULT — the vLLM ladder, EXERCISED, 2026-09-08** *(was PHASE 11 · D15)* — [detail →](docs/execution-log.md#67d15-result-the-vllm-ladder-exercised-2026-09-08-was-phase-11-d15)
  - ⚠️ **D15.0 · A defect found on the way: `make up-vllm` re-downloaded a 30 GB image** — [detail →](docs/execution-log.md#d150-a-defect-found-on-the-way-make-up-vllm-re-downloaded-a-30-gb-image)
  - ✅ **D15.1 · The D14.1 warning is gone — the run now inspects the chain it names** — [detail →](docs/execution-log.md#d151-the-d141-warning-is-gone-the-run-now-inspects-the-chain-it-names)
  - ✅ **D15.2 · The full ladder, on vLLM** — [detail →](docs/execution-log.md#d152-the-full-ladder-on-vllm)
  - ⚠️ **D15.3 · The vLLM run exposed a THIRD instrument defect: a green spend check** — [detail →](docs/execution-log.md#d153-the-vllm-run-exposed-a-third-instrument-defect-a-green-spend-check)
  - ✅ **Running tally of instrument defects found by RUNNING the scripts** — [detail →](docs/execution-log.md#running-tally-of-instrument-defects-found-by-running-the-scripts)
  - ✅ **D15.4 · Confirmation re-run — `PASS=59 · PROVES NOTHING=1 · FAIL=0`** — [detail →](docs/execution-log.md#d154-confirmation-re-run-pass59-proves-nothing1-fail0)
  - ✅ **Both engines, both ladders, final state** — [detail →](docs/execution-log.md#both-engines-both-ladders-final-state)
- ✅ **6.8 · Full inspection run + the FIRST real application bug, 2026-09-09** *(was PHASE 13)* — [detail →](docs/execution-log.md#68-full-inspection-run-the-first-real-application-bug-2026-09-09-was-phase-13)
  - 🔴 **A1 · APPLICATION BUG — a confident Washington DC itinerary labelled "Nara"** — [detail →](docs/execution-log.md#a1-application-bug-a-confident-washington-dc-itinerary-labelled-nara)
  - 📌 **A2 · The kill switch had been left ON** — [detail →](docs/execution-log.md#a2-the-kill-switch-had-been-left-on)
  - ⚠️ **Defects #12-#14 — three more instrument bugs, none in the app** — [detail →](docs/execution-log.md#defects-12-14-three-more-instrument-bugs-none-in-the-app)
  - ✅ **A3 · `docs/INSPECTION.md` battery — 7/8 PASS (`scripts/battery.py`, new)** — [detail →](docs/execution-log.md#a3-docsinspectionmd-battery-78-pass-scriptsbatterypy-new)
  - ✅ **A4 · `docs/INSPECTION_DEEP.md` — `PASS=59 · FAIL=0 · EXIT=0`** — [detail →](docs/execution-log.md#a4-docsinspection_deepmd-pass59-fail0-exit0)
  - ⚠️ **A5 · Auth consent — TWO stacked causes, both now removed** — [detail →](docs/execution-log.md#a5-auth-consent-two-stacked-causes-both-now-removed)
  - ✅ **Running tally** — [detail →](docs/execution-log.md#running-tally)
- ✅ **6.9 · RedisInsight auto-registration — user-reported, 2026-09-09** *(was PHASE 13 cont.)* — [detail →](docs/execution-log.md#69-redisinsight-auto-registration-user-reported-2026-09-09-was-phase-13-cont)
  - ⚠️ **Cause 1 · RedisInsight had NO volume** — [detail →](docs/execution-log.md#cause-1-redisinsight-had-no-volume)
  - ⚠️ **Cause 2 · Storing ANY password failed with a misleading 500** — [detail →](docs/execution-log.md#cause-2-storing-any-password-failed-with-a-misleading-500)
  - ⚠️ **Cause 3 · Nothing registered them** — [detail →](docs/execution-log.md#cause-3-nothing-registered-them)
  - ✅ **Proven end to end from a WIPED state** — [detail →](docs/execution-log.md#proven-end-to-end-from-a-wiped-state)
  - ✅ **Why the NAMES matter, not just the connection** — [detail →](docs/execution-log.md#why-the-names-matter-not-just-the-connection)

## PHASE 7 — Deployment on the local machine *(was PHASE 6; now absorbs PHASE 12 · K)*

- ✅ **7.1 Docker Compose, split by concern**
  - ✅ 7.1.1 `docker-compose.data.yml` — Postgres, Redis, Qdrant, Overpass
  - ✅ 7.1.2 `docker-compose.app.yml` — api, worker, web
  - ✅ 7.1.3 `docker-compose.observability.yml`
  - ✅ 7.1.4 `docker-compose.gpu.yml` — added this session (see 5.4.1)
- ✅ **7.2 Local Kubernetes (kind)** — `scripts/kind-up.sh` / `kind-down.sh`, `infra/kind/`
  - 🔄 7.2.1 **Image drift unreconciled** — `.env` pins `v1.31.2`, the cluster runs `v1.31.6`
- ✅ **7.3 Helm chart** — `infra/helm/voyantra/templates/`, 11 templates
  - ✅ 7.3.1 Workloads — `api.yaml` · `worker.yaml` · `web.yaml`
  - ✅ 7.3.2 Data — `postgres.yaml` · `redis.yaml`
  - ✅ 7.3.3 Config + secrets — `configmap.yaml` · `secret.yaml` · `externalsecret.yaml`
  - ✅ 7.3.4 Identity — `serviceaccount.yaml` (IRSA)
- ✅ **7.4 Terraform / AWS** — `infra/terraform/`, 10 files
  - ✅ 7.4.1 Network — `vpc.tf`, plus providers / versions / variables / outputs
  - ✅ 7.4.2 Compute — `eks.tf`
  - ✅ 7.4.3 Data — `rds.tf` · `elasticache.tf`
  - ✅ 7.4.4 Registry — `ecr.tf`
  - ✅ 7.4.5 Identity — `irsa.tf`
  - ⏳ 7.4.6 **GPU node group + scale-to-zero** — not written
- ✅ **7.5 ArgoCD GitOps** — `infra/argocd/`
  - ✅ 7.5.1 `project.yaml` + `application-dev/staging/prod.yaml`
  - ⏸️ 7.5.2 **Cloud apply is user-run** — never executed from here
- ✅ **7.6 CI/CD** — `.github/workflows/`
  - ✅ 7.6.1 `ci.yml` — lint, types, tests
  - ✅ 7.6.2 `cd.yml` — build, push, deploy
  - ✅ 7.6.3 `promote.yml` — dev -> staging -> prod behind the eval gate

- ✅ **7.7 · kind wired into the composite lifecycle, 2026-09-08** *(was PHASE 12 · K)* — [detail →](docs/execution-log.md#77-kind-wired-into-the-composite-lifecycle-2026-09-08-was-phase-12-k)
  - ✅ **Verified state BEFORE the change** — [detail →](docs/execution-log.md#verified-state-before-the-change)
  - ✅ **K0 · SAFETY FIRST — can this Makefile harm another project's cluster?** — [detail →](docs/execution-log.md#k0-safety-first-can-this-makefile-harm-another-projects-cluster)
  - ✅ **BEFORE                          ### AFTER** — [detail →](docs/execution-log.md#before-after)
  - ✅ **K1 · `KIND ?= 1` knob** — [detail →](docs/execution-log.md#k1-kind-1-knob)
  - ✅ **K2 · `kind-start` — create if absent, else RESTART stopped nodes** — [detail →](docs/execution-log.md#k2-kind-start-create-if-absent-else-restart-stopped-nodes)
  - ✅ **K3/K4 · `kind-stop` (preserves) and `kind-status`** — [detail →](docs/execution-log.md#k3k4-kind-stop-preserves-and-kind-status)
  - ✅ **K5 · Wired into the lifecycle** — [detail →](docs/execution-log.md#k5-wired-into-the-lifecycle)
  - ✅ **K6 · `infra` / `infra-down` kept as aliases** — [detail →](docs/execution-log.md#k6-infra-infra-down-kept-as-aliases)
  - ⏳ **K7 · NOT yet proven — stated honestly** — [detail →](docs/execution-log.md#k7-not-yet-proven-stated-honestly)

## PHASE 8 — Deployment on a real, non-AWS managed Kubernetes cluster

> **Why this phase exists.** kind proves everything *above* the substrate and nothing below it
> (`docs/deployment-scaling-plan.md` · A1). This phase buys the other third: a real LoadBalancer,
> real CSI storage, real DNS/TLS, real managed data, real node pools, real autoscaling — and a
> real bill. Target venue: **DigitalOcean DOKS**, funded by the $200 credit.
> Full reasoning, costings and vendor comparison: `docs/deployment-scaling-plan.md`.

- ⏳ **8.1 Close the four chart gaps** *(this is why it is a phase, not a `terraform apply`)*
  - ⏳ 8.1.1 `templates/ingress.yaml` — **no Ingress exists in the chart today**
  - ⏳ 8.1.2 `templates/hpa.yaml` + KEDA `ScaledObject` on Celery queue depth — **no autoscaling exists**
  - ⏳ 8.1.3 `templates/qdrant.yaml` — Qdrant lives only in `docker-compose.data.yml`, not the chart
  - ⏳ 8.1.4 `templates/pdb.yaml` — PodDisruptionBudgets for node drain
- ⏳ **8.2 Split the Terraform root** *(no abstraction layer — deliberate; plan · A4)*
  - ⏳ 8.2.1 Move the existing 11 `.tf` unchanged into `infra/terraform/aws/`
  - ⏳ 8.2.2 New `infra/terraform/do/` — DOKS + node pool + VPC + firewall
  - ⏳ 8.2.3 Managed Postgres + managed Valkey; DOCR registry
  - ⏳ 8.2.4 Both roots emit the same five outputs: `kubeconfig` · `database_url` · `redis_url` · `registry_endpoint` · `workload_identity_annotation`
  - ⏳ 8.2.5 **IRSA has no DO equivalent** — fall back to ESO + a real secret backend, and *document the security downgrade* rather than paper over it
- ⏳ **8.3 Cluster addons** — ingress-nginx · cert-manager (Let's Encrypt) · External Secrets Operator · metrics-server · KEDA
- ⏳ **8.4 Bring-up** — Shape B first (2 nodes, in-cluster PG/Redis, ~$65/mo), then Shape A (3 nodes + managed data, ~$119/mo) for the evidence run
- ⏳ **8.5 Cost + teardown discipline** *(highest-leverage item in the phase)*
  - ⏳ 8.5.1 Billing alerts at $50 / $100 / $150 — **before the first apply**
  - ⏳ 8.5.2 `make cloud-up` / `make cloud-down` wrapping `terraform apply` / `destroy`
  - ⏳ 8.5.3 `pg_dump` before every destroy; restore on bring-up
  - ⏳ 8.5.4 `LAST_APPLY` timestamp — a cluster up longer than a working day is a bug
  - ⏳ 8.5.5 Paste every `terraform destroy` output here as proof
- ⏳ **8.6 Evidence run** — all 12 artifacts from `docs/deployment-scaling-plan.md` · A7, into `docs/evidence/`
  - ⏳ 8.6.1 Real nodes / pod spread across zones
  - ⏳ 8.6.2 **Autoscaling under k6 load** — replica count before → during → after + Grafana panel
  - ⏳ 8.6.3 **k6 at 30–50 concurrent plans** — p50/p95/p99, error rate, cost per plan
  - ⏳ 8.6.4 **Rollback drill** — `kubectl rollout undo`, zero-downtime proof
  - ⏳ 8.6.5 **Chaos drill** — kill a worker mid-run, prove the LangGraph checkpointer resumes
  - ⏳ 8.6.6 **Restore drill** — managed-PG restore from backup, timed
  - ⏳ 8.6.7 Ingress + TLS — `curl -vI https://…`, valid chain
  - ⏳ 8.6.8 Cost report — `$ per 1k plans`, final bill, teardown record


---

## PHASE 9 — Deployment on AWS (EKS)

> **Why after PHASE 8.** `infra/terraform/` already targets AWS, so this phase is largely
> *validation of work already written* — plus the one thing only AWS gives: **IRSA**. "EKS" is
> also the keyword hiring filters match on. Run it deliberately, capture evidence, destroy it.
> This is the most expensive venue in the plan and should be the shortest visit.

- ⏳ **9.1 Preconditions** — AWS account, budget alarms, `infra/terraform/aws/` (moved in 8.2.1), the four chart templates from 8.1 already proven on DOKS
- ⏳ **9.2 `terraform apply`** — VPC → EKS → RDS → ElastiCache → ECR → IRSA *(user-run; carries forward 7.5.2 (old 6.5.2))*
- ⏳ **9.3 IRSA end-to-end** — the one capability DO cannot provide; prove a pod assumes an IAM role with no static credentials
- ⏳ **9.4 GPU node group** — `gpu.tf` **is written and validated but was never planned** *(carries forward 7.4.6 (old 6.4.6), whose "not written" wording was stale — see 6.6 · R4.2)*; plan + apply + scale-to-zero, or explicitly defer
- ⏳ **9.5 ArgoCD app-of-apps against the real cluster** — dev → staging → prod behind the eval gate
- ⏳ **9.6 Evidence run** — the A7 set again on EKS, plus the IRSA proof; note the cost delta vs DOKS
- ⏳ **9.7 Cost + teardown** — `terraform destroy`, final bill, and the honest EKS-vs-DOKS cost comparison written up


---
## PHASE 10 — Postmortem & portfolio writeup *(was PHASE 7; REOPENED — see 10.6)*

- ✅ **10.1 Case study written** — `case-study.md`
- ✅ **10.2 Portfolio README** — `README2.md`; public `README.md` in tree
- ✅ **10.3 Screenshots captured** — `screenshots/`
- ✅ **10.4 Internal labels neutralised for publication** — commit `8187988`
- ✅ **10.5 Private planning notes untracked** — commits `02b19e5`, `c676002`, `3424619`

---


- 🔄 **10.6 REOPENED by the 2026-09-09 restructure** — the case study was written *before* the
  real-cluster phases existed. It currently understates the work and cannot claim production
  Kubernetes. Reopen once PHASES 8–9 land:
  - ⏳ 10.6.1 Fold in the PHASE 8 evidence set (real nodes, autoscaling under load, chaos + restore drills)
  - ⏳ 10.6.2 Fold in the PHASE 9 IRSA proof and the EKS-vs-DOKS cost comparison
  - ⏳ 10.6.3 Replace every "would scale to" claim with a measured number, or delete it
  - ⏳ 10.6.4 Add the capacity model (plan · A2) as the scaling narrative, labelled as a model
  - ⏳ 10.6.5 State plainly which tiers are demonstrated and which are architecture-on-paper


---
