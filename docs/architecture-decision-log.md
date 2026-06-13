# Architecture Decision Log — AI Travel Planner (Agentic RAG hybrid)

> Status: **Phase 2 of the v4 Portfolio→Production transformation.** Target = production-grade **Agentic RAG hybrid** (Service Package 2 × 1): a multi-agent, multi-city travel planner that grounds itineraries in real POIs/weather/routing.
> Anchored to the locked Phase 1 NFRs: design for ~1M MAU / ~500 peak concurrent (demonstrate ~50 via k6); quality-first ≤ **$0.30/itinerary**; multi-city (≤5 cities, ≤10 days); full-itinerary p95 45s; 99.5% SLO; GDPR-aligned hygiene; ≤ ~$50/mo idle dev.

## At-a-glance summary (all 22)

| # | Decision | Options considered | Picked | Why (short) | Prod-grade? | Gap-closed? | Reversibility |
|---|---|---|---|---|---|---|---|
| 1 | Primary DB | Postgres / DynamoDB / MongoDB | **Postgres (Aurora)** | Relational run→city→step hierarchy + audit + LangGraph checkpoint store | Yes | — | Moderate-Hard |
| 2 | Vector DB | Qdrant / pgvector / Pinecone / Milvus / Weaviate | **Qdrant** (~1024-dim, hybrid) | Filtered hybrid search at scale; multilingual multi-city | Yes | Yes (vector ops) | HARD once loaded |
| 3 | Agent architecture | ReAct / plan-execute graph / **multi-agent** | **Multi-agent** (coordinator + per-city workers + critic) | Clean multi-city decomposition, parallel fan-out, central critic | Yes | Yes (multi-agent) | Moderate-Hard |
| 4 | LLM provider & tiering | single frontier / **tiered+fallback gateway** / open-weight | **Gateway**: Haiku→Sonnet→Opus 4.8; fallback Anthropic→Groq→OpenAI | Quality where it counts + cost control + SLO resilience | Yes | Yes (serving/cost) | Easy-Moderate |
| 5 | Embedding model | **Voyage** / Cohere / OpenAI-3-large / bge-m3 | **Voyage voyage-3** (~1024-dim; bge-m3 fallback same dim) | Multilingual retrieval; small vectors; Anthropic-aligned | Yes | Yes | HARD (re-embed) |
| 6 | Orchestration | **LangGraph** / thin loop / CrewAI | **LangGraph** (supervisor/worker; tools framework-agnostic) | Durable checkpoints + HITL + parallel; your skill | Yes | — | Moderate |
| 7 | Backend | **FastAPI** / Node / Go | **Python + FastAPI** (async, Pydantic v2, REST+SSE) | One language with the AI core; I/O-bound | Yes | — | Hard (language) |
| 8 | Frontend & streaming | **Next.js** / Svelte / keep Streamlit | **Next.js** + Tailwind/shadcn + SSE + MapLibre (Streamlit=dev-only) | Trace UX is the product; portfolio signal | Yes | — | Moderate |
| 9 | Auth | Clerk / Cognito / **Auth0** | **Auth0** (OIDC/JWT/Orgs; Cognito AWS-native alt) | Mature, enterprise SSO, recognizable | Yes | — | Moderate |
| 10 | Caching | **Redis** / Memcached / none | **Redis**: semantic + embedding + tool-result; + Anthropic prompt cache | Biggest cost lever; reuse as broker | Yes | Yes (cost/scale) | Easy |
| 11 | Queue & async | ARQ / **Celery** / SQS / Temporal | **Celery + Redis broker** (RabbitMQ alt; KEDA autoscale) | Mature; your skill; reuse Redis | Yes | — | Moderate |
| 12 | Inference serving | **hosted APIs** / vLLM / SageMaker | **Hosted APIs behind gateway** (Anthropic direct; Bedrock alt); vLLM future | No idle GPU; full prompt-cache+tool parity | Yes | — | Easy |
| 13 | Observability | **OTel+Langfuse** / LangSmith / CloudWatch | **OTel → Prom/Grafana + Loki; Langfuse** (LangSmith alt) | Per-step agent tracing; closes Langfuse gap; fixes log disconnect | Yes | Yes (observability) | Easy-Moderate |
| 14 | Cloud | **AWS** / GCP / Azure | **AWS** (EKS, Aurora, ElastiCache, S3, ECR, Secrets Mgr, CloudFront, R53, ALB, WAF) | Your axis + positioning; covers everything | Yes | — | Hard |
| 15 | Containers/IaC | **EKS** / ECS Fargate / Fly | **Docker multi-stage → EKS**; Terraform + Helm + ArgoCD | Production-K8s is the named gap; scale | Yes | Yes (prod K8s) | Moderate-Hard |
| 16 | CI/CD | **GitHub Actions** / GitLab / Jenkins | **GH Actions + ArgoCD + Argo Rollouts**; mandatory eval gate | Industry default; eval gate = production | Yes | Yes (MLOps/CD) | Easy-Moderate |
| 17 | Secrets/config | **Secrets Mgr+ESO** / k8s Secrets / Vault | **AWS Secrets Manager + ESO + pydantic-settings (fail-fast)** | Out of repo, rotatable; fixes Phase-0 config bug | Yes | Yes (security) | Easy-Moderate |
| 18 | Security/threat | defense-in-depth | **Agentic threat model**: untrusted retrieval, tool-authz least-priv, structured tool I/O, v1 read-only tools, PII redaction, WAF/TLS/mTLS, audit, injection suite | Yes | Yes (security) | Moderate |
| 19 | Evaluation | layered | **RAGAS + agent-trajectory + LLM-judge** on versioned golden sets; CI gate; online sampling + drift; A/B; adversarial | Yes | Yes (eval — serious gap) | Easy |
| 20 | Cost controls | defense-in-depth | **Tiering+caching levers; per-run & per-sub-agent hard caps; Task Budgets; per-tenant quotas+rate limits; spend alerts + kill switch; prove <$0.30** | Yes | Yes (cost eng) | Easy |
| 21 | Failure/degradation | per-failure matrix | **Circuit breakers + retries/backoff + timeouts; partial results; honest no-answer; backpressure + bulkheads; cross-provider fallback** | Yes | Partial (distributed) | Easy-Moderate |
| 22 | Repo structure | mono vs poly | **uv monorepo**: apps/(web,api,worker,ingestion) + packages/(agents,tools,core,retrieval,eval) + infra + tests + docs | Yes | — | Moderate |

Legend: "Gap-closed?" = closes a gap named in `Prompts/01-career-assessment.md`. Reversibility = cost to change later.

---

## Full entries

### Decision 1: Primary database
- **Question:** Durable system-of-record for users, runs, per-city sub-agent state, tool audit, feedback, eval.
- **Options:** Postgres (relational, JSONB, LangGraph checkpointer) / DynamoDB (serverless, no joins) / MongoDB (document).
- **Decision:** **Postgres 16 (Aurora/RDS).** JSONB for step/tool payloads; `langgraph-checkpoint-postgres` for durable, resumable multi-agent state in the same transactional DB.
- **Reasoning:** Multi-agent multi-city runs are hierarchical + audit-heavy → relational. Co-locating checkpoint + business state = one backup/restore + real resumability.
- **Trade-offs:** Operate a stateful DB vs serverless Dynamo — accepted for queryability + audit.
- **Reversibility:** Moderate-Hard (schema migration); low-regret default.

### Decision 2: Vector database
- **Question:** Where the ~1024-dim Voyage POI vectors live, with hybrid + heavy filtering.
- **Options:** Qdrant / pgvector / Pinecone / Milvus / Weaviate / OpenSearch.
- **Decision:** **Qdrant** (~1024-dim, dense+sparse hybrid, payload filters: city/interest/lang/ACL/source/season). Retrieval: filtered top-k≈20 → rerank → top≈5. Behind a `VectorStore` interface. Reranker: Cohere Rerank (default) / bge-reranker (self-host); + MMR for diversity. pgvector kept for incidental vectors.
- **Reasoning:** Multi-city quality-first retrieval lives on filtering + hybrid at scale; dimension pinned by #5 makes a future engine swap a re-index, not a re-embed.
- **Trade-offs:** A second datastore vs pgvector simplicity — accepted for retrieval quality at scale.
- **Reversibility:** HARD once loaded; mitigated by the interface + reproducible ingestion.

### Decision 3: Agent architecture  *(REVISED → Multi-agent)*
- **Question:** Agent control flow for the confirmed Agentic-RAG-hybrid.
- **Options:** ReAct loop / plan-execute graph (single agent) / **multi-agent**.
- **Decision:** **Multi-agent** — coordinator/supervisor + one worker sub-agent per city (geocode→POIs→weather→intra-city route) + a critic sub-agent (validates merged multi-city plan, inter-city legs, feasibility, groundedness) → corrective loop.
- **Containment contract:** ≤5 city workers; hard per-sub-agent step/token/time caps; deterministic typed tool contracts; **graceful partial results** (one city fails → return the rest + flag); critic loop capped at N rounds; per-sub-agent trajectory eval.
- **Reasoning:** Multi-city decomposes along city boundaries → parallel fan-out (helps p95) + central critic. Most impressive artifact; consistent with the maximalist target. Build the single-agent path first (thin slice), then widen → always a working fallback architecture.
- **Trade-offs:** Reliability is a named gap + cost pressure on the $0.30 ceiling — accepted WITH the containment contract + raised eval bar.
- **Reversibility:** Moderate-Hard (structural).

### Decision 4: LLM provider & model-tiering  *(REVISED fallback order: Groq → OpenAI)*
- **Question:** Models, tiering, fallback under quality-first ≤$0.30 + 99.5% SLO.
- **Options:** single frontier / **tiered + cross-provider fallback gateway** / open-weight self-host.
- **Decision:** Model **gateway** with 3-tier Anthropic routing by step difficulty — **Haiku 4.5** ($1/$5) routine sub-steps → **Sonnet 4.6** ($3/$15) composition → **Opus 4.8** ($5/$25, adaptive thinking) multi-city planning + corrective check. Frontier defaults to **Opus 4.8**, NOT Fable 5 ($10/$50, manual escalation only). Cross-provider fallback chain: **Anthropic → Groq → OpenAI** (Groq first = cheap/fast failover; OpenAI = deeper quality fallback). Aggressive Anthropic prompt caching = primary cost lever.
- **Reasoning:** Quality-first = frontier on quality-critical steps, cheap on routine fan-out. Caching cuts repeated context to ~0.1×. Single-provider can't hit 99.5% → gateway fallback is load-bearing. (Anthropic's server-side `fallbacks` is refusal-only + Opus-only → complements, doesn't replace, cross-provider outage fallback.)
- **Trade-offs:** Router is a moving part + eval surface — accepted to satisfy both cost ceiling and SLO.
- **Reversibility:** Easy-Moderate (config behind the gateway).

### Decision 5: Embedding model  *(MOST EXPENSIVE TO REVERSE)*
- **Question:** Embeds POI/travel corpus + queries; dimension baked into the vector DB.
- **Options:** **Voyage voyage-3** / Cohere embed v3 / OpenAI text-embedding-3-large / self-host bge-m3.
- **Decision:** **Voyage voyage-3** (multilingual, lock ~1024-dim at provisioning). **bge-m3 self-host is the documented fallback at the SAME dimension** so a cost/residency-driven swap doesn't force a re-embed.
- **Reasoning:** Multi-city = multilingual → multilingual retrieval is non-negotiable; Voyage/Cohere lead, OpenAI-3-large is English-leaning + 3072-dim (3× vector RAM). Voyage is Anthropic's recommended pairing.
- **Trade-offs:** +1 vendor — accepted for retrieval quality.
- **Reversibility:** HARD (re-embed). Mitigation: version embedding config, pin dimension, same-dim fallback.

### Decision 6: Orchestration framework
- **Options:** **LangGraph** / thin custom loop (Anthropic tool-runner) / CrewAI-AutoGen.
- **Decision:** **LangGraph** (supervisor / orchestrator-worker with subgraphs + checkpointing + HITL interrupts + parallel nodes). Tools kept as plain typed Python functions (framework-agnostic).
- **Reasoning:** Multi-agent reliability needs durable checkpoints + HITL + parallel fan-out — LangGraph gives all three natively; your deepest skill. Keeping tools portable de-risks orchestration lock-in.
- **Trade-offs:** Heavier dep than a custom loop — accepted for checkpointing + HITL.
- **Reversibility:** Moderate (tools portable; graph wiring is the LangGraph-specific part).

### Decision 7: Backend language & framework
- **Options:** **Python + FastAPI** / Node (NestJS/Hono) / Go.
- **Decision:** **Python + FastAPI** (async, Pydantic v2 at all boundaries). REST for commands/CRUD + **SSE** for streaming the agent trace. Service split (monorepo): `api`, `ingestion`, `worker`.
- **Reasoning:** The whole brain is Python; a non-Python gateway adds a serialization boundary per agent step. Work is I/O-bound (LLM + tools), so Python's CPU ceiling never bites. Split ingestion/query/worker so each scales independently.
- **Reversibility:** Hard (language) — won't change; service split keeps pieces replaceable.

### Decision 8: Frontend & streaming UX
- **Options:** **Next.js** / SvelteKit-Remix-Nuxt / keep Streamlit.
- **Decision:** **Next.js** (App Router, TS) + Tailwind + shadcn/ui + TanStack Query + Zustand. SSE (EventSource) streams the agent trace; **MapLibre** map (Mapbox alt); AbortController cancel; HITL approve/edit/reject; run history. **Streamlit demoted to internal/dev harness only.**
- **Reasoning:** A multi-agent planner's transparency is the value + the portfolio wow; Next.js gives streaming + map + auth integration + résumé signal. Streamlit can't render the trace credibly.
- **Reversibility:** Moderate (contained rewrite; the SSE/REST contract is the durable part).

### Decision 9: Authentication & authorization  *(REVISED → Auth0)*
- **Options:** Clerk / Cognito / **Auth0** / self-rolled.
- **Decision:** **Auth0** (OIDC/JWT, Organizations for multi-tenancy, enterprise SSO/SAML). Cognito = documented AWS-native alt (flip trigger: identity data must stay in client AWS / residency / cost at scale). FastAPI validates the JWT in one auth dependency; RBAC; **ACL-at-retrieval** in Qdrant; per-tenant quotas; GDPR deletion path.
- **Reasoning:** Mature, recognizable, enterprise-SSO — credible for enterprise-adjacent clients; supports GDPR story. Behind one seam so the Cognito swap is cheap.
- **Trade-offs:** Pricier/heavier than Clerk + 3rd-party egress vs Cognito coherence — accepted for maturity.
- **Reversibility:** Moderate.

### Decision 10: Caching strategy
- **Options:** **Redis** / Memcached / none.
- **Decision:** **Redis (ElastiCache)** — (1) semantic answer cache [strict similarity threshold + key = {cities,interests,dates,constraints} to avoid wrong-city hits], (2) embedding cache, (3) per-tool result cache (geocode ~∞, POI ~days, weather ~hours, routing ~days). Plus provider-side **Anthropic prompt caching** of system+tools+retrieved-context prefix (~0.1× reads).
- **Reasoning:** Repeated tool lookups + repeated context across requests → caching is what keeps Opus planning under $0.30. Redis also brokers the queue (#11).
- **Reversibility:** Easy. **Watch-out:** loose semantic-cache similarity returns confidently-wrong plans → strict threshold + full key + eval-on-hit.

### Decision 11: Queue & async work  *(REVISED → Celery)*
- **Options:** ARQ / **Celery** / SQS / Temporal.
- **Decision:** **Celery + Redis** broker + result backend (RabbitMQ alt for stronger guarantees). KEDA autoscales workers on queue depth; per-tenant concurrency caps. Each Celery task drives the async graph via `asyncio.run(graph.ainvoke(...))`. Division: Celery = dispatch/scale/retry; LangGraph+Postgres = in-run state/resume. Temporal = future durability upgrade.
- **Reasoning:** Mature, your skill; reuse Redis. Keep tasks thin so the async↔Celery bridge stays simple.
- **Reversibility:** Moderate.

### Decision 12: Inference serving
- **Options:** **hosted APIs behind gateway** / self-host vLLM / all-SageMaker.
- **Decision:** **Hosted provider APIs behind the gateway** — Anthropic direct primary (full prompt-cache + tool-use + structured-output parity), AWS Bedrock the AWS-native/residency alt. **vLLM self-host = documented scale-out path** (designed for, not built in v1).
- **Reasoning:** Idle GPU breaks the ≤$50/mo budget; hosted scales to zero. Gateway lets a vLLM cheap-tier slot in later at real volume — "architect for scale, demonstrate small."
- **Reversibility:** Easy (add a backend via config).

### Decision 13: Observability
- **Options:** **OTel + Langfuse** / OTel + LangSmith / CloudWatch+X-Ray.
- **Decision:** **OpenTelemetry** (traces/metrics/logs) through FastAPI + Celery + the agent; **Prometheus + Grafana** (metrics); **Loki** (structured JSON to STDOUT — fixes the Phase-0 file-logging/ELK disconnect); **Langfuse** for agent/LLM tracing (LangSmith = native-LangGraph alt; ELK = alt since original used it). Alertmanager → Slack/PagerDuty. Trace: plan → per-city sub-agent tool calls → tokens/cost/latency/tier/cache → critic verdict + correction rounds + partial flags. SLO/error-budget alerts on runaway runs, tool-error spikes, p95 breach.
- **Reasoning:** Multi-agent is the highest-observability package; observability + Langfuse are named gaps → double gap-closer. OTel keeps backends swappable.
- **Reversibility:** Easy-Moderate.

### Decision 14: Cloud provider & core services
- **Options:** **AWS** / GCP / Azure.
- **Decision:** **AWS** — EKS, Aurora Postgres, ElastiCache Redis, S3, ECR, Secrets Manager, CloudFront, Route 53, ALB, VPC + WAF. LLM via hosted APIs (Bedrock = AWS-native Claude path). Qdrant on EKS or Qdrant Cloud.
- **Reasoning:** Your strongest axis + positioning; nothing compelling off-AWS for this app; one cloud reduces solo ops surface.
- **Reversibility:** Hard (cloud); bounded by Terraform + container/k8s portability.

### Decision 15: Containers, orchestration & IaC
- **Options:** **EKS** / ECS Fargate / Fly-CloudRun.
- **Decision:** **Docker multi-stage / non-root** (fixes Phase-0 Dockerfile; add healthcheck + .dockerignore) → **AWS EKS.** Terraform modular (`vpc/eks/data/app`); Helm charts; ArgoCD GitOps. ECS Fargate = simpler swap.
- **Cost reality:** an always-on EKS cluster (~$73/mo control plane + nodes) breaks ≤$50/mo. Mitigation (Phase 6): dev on local kind/minikube; stand EKS up for staging/prod demo + the k6 load test; scale nodes to ~zero / tear down between sessions. EKS is the demonstrated target, not 24/7 idle.
- **Reasoning:** Production EKS is the named gap between Minikube and a real cluster + the scale platform + the résumé signal. You know Helm + ArgoCD.
- **Reversibility:** Moderate-Hard (Terraform + portable containers keep EKS→ECS viable).

### Decision 16: CI/CD pipeline
- **Options:** **GitHub Actions** / GitLab CI / Jenkins.
- **Decision:** **GitHub Actions** (build/test/scan/push) + **ArgoCD** (GitOps) + **Argo Rollouts** (canary). Trunk-based + PR checks. Pipeline: lint/type → unit → integration → build → **Trivy scan** → push ECR → deploy staging → **EVAL GATE (RAGAS + agent-trajectory) blocks on regression** → promote prod → smoke → canary w/ auto-rollback. Envs: dev/staging/prod.
- **Reasoning:** Industry default + your stack. The mandatory eval gate is what makes it production, not demo.
- **Reversibility:** Easy-Moderate.

### Decision 17: Secrets & configuration
- **Options:** **Secrets Manager + ESO + pydantic-settings** / k8s Secrets only / Vault.
- **Decision:** **AWS Secrets Manager** (KMS + rotation) as source of truth; **External Secrets Operator** syncs to K8s; **pydantic-settings** typed config that **fails fast on a missing key** (fixes Phase-0 silent `GROQ_API_KEY=None`). `.env` local-dev only (gitignored; commit `.env.example`). Vault = future upgrade.
- **Reasoning:** Many secrets now (Anthropic/Groq/OpenAI/Voyage/Cohere/Auth0/DB/Redis/Langfuse). Keep them out of the repo + rotatable; make bad config a startup crash.
- **Reversibility:** Easy-Moderate.

### Decision 18: Security posture & threat model
- **Decision:** Defense-in-depth. Agentic core: treat retrieved/tool content as untrusted data (not instructions); per-agent tool allowlist; retrieved text never directly triggers a privileged tool; strict Pydantic tool I/O; **v1 tools are READ-ONLY** (bounded blast radius; future write/booking ⇒ HITL + sandbox). PII redaction (Presidio) before traces/logs. WAF + TLS + mTLS + VPC isolation. Append-only audit of every tool action + query. Prompt-injection test suite gated in CI.
- **Reasoning:** Agents act via tools → tool layer + untrusted retrieval is the center of gravity; read-only v1 tools are the biggest blast-radius reducer.
- **Reversibility:** Moderate. *(Closes a named gap.)*

### Decision 19: Evaluation strategy
- **Decision:** Layered. Offline CI gate: **RAGAS** (grounding) + **agent-trajectory/task-success** (valid multi-city plan? success/steps/cost/coverage/grounded/feasible/critic-catches-planted-error) + **DeepEval/promptfoo** (prompt regression) + **LLM-as-judge** (calibrated) for subjective quality. Versioned golden sets (single/multi-city, languages, edge cases). Online: prod sampling → groundedness/feasibility → drift alerts; eval-on-cache-hit. A/B behind flags. Adversarial/injection suite. Tooling: Langfuse datasets + RAGAS + DeepEval/promptfoo + custom trajectory runner.
- **Reasoning:** Eval separates demo from trustworthy; multi-agent makes trajectory eval non-optional. Highest-leverage gap-closer.
- **Reversibility:** Easy. *(Closes a named SERIOUS weakness.)*

### Decision 20: Cost controls
- **Decision:** Levers: model tiering (#4) + caching (#10, incl. Anthropic prompt cache). Hard caps: per-run AND per-sub-agent token/dollar/step caps; Anthropic Task Budgets + enforced max. Per-tenant token quotas + per-user rate limits (slowapi/Redis). Spend dashboards (cost/itinerary, cost/sub-agent) + anomaly alerts + **global/per-tenant kill switch** (alert before, not after). Batch API (50% off) for offline enrichment. **Prove cost/itinerary < $0.30 in eval as a gate.**
- **Reasoning:** Multi-agent × frontier × multi-city is worst-case cost; hard per-sub-agent caps + caching keep it under ceiling.
- **Reversibility:** Easy. *(Closes a named gap.)*

### Decision 21: Failure-mode & degradation
- **Decision:** Per-failure matrix — LLM down → cross-provider fallback (Anthropic→Groq→OpenAI) → queue/cached/honest error; tier rate-limited → backoff+retry→next provider; vector DB down → timeout+circuit-breaker → live-POI-tool-only (flagged); retrieval empty → live tool → honest no-answer (never hallucinate); tool fails → retry+breaker → graceful degrade (flag); **one city sub-agent fails → partial results** (others + flag); critic non-convergence → cap rounds → best-effort + "not verified" flag; injection input → guardrails; queue saturation → backpressure + per-tenant bulkheads + KEDA. Patterns: timeouts, retries w/ backoff+jitter, circuit breakers (tenacity), bulkheads, idempotent dispatch, honest messaging. Each row → a Phase-5 runbook.
- **Reasoning:** 99.5% on external providers needs explicit fallbacks; multi-agent needs partial-result handling.
- **Reversibility:** Easy-Moderate. *(Partial: distributed-systems resilience.)*

### Decision 22: Repo structure
- **Decision:** **uv monorepo** — `apps/`(web, api, worker, ingestion) · `packages/`(agents, tools [revived `tp_tools`], core [pydantic settings + LLM gateway + schemas + logging], retrieval [behind VectorStore interface], eval) · `infra/`(terraform, k8s) · `.github/workflows/`(ci, eval-gate, cd) · `tests/`(unit, integration, e2e, load, injection) · `docs/`. Prompts versioned in-repo + Langfuse registry. Tools framework-agnostic.
- **Reasoning:** Monorepo fits a solo builder; ~60% baseline shared; interface boundaries on hard-to-reverse pieces.
- **Reversibility:** Moderate.

---

## Revisions during Phase 2
- **#3** single-agent graph → **multi-agent** (user choice; maximalist).
- **#4** fallback order OpenAI-then-Groq → **Groq-then-OpenAI** (user choice; matches prior LiteLLM work).
- **#9** Clerk → **Auth0** (user choice; maturity/recognizability).
- **#11** ARQ → **Celery + Redis** (user choice; existing skill).

## Amendments during Phase 4
- **#4 / #17 (S2)** Provider availability: only an **OpenAI** API key is on hand → **OpenAI is the primary tier** (cheap `gpt-4o-mini`, mid+frontier `gpt-4o` — model IDs are config to verify); Anthropic + Groq become **optional fallback rungs** (inert until their key is set). Gateway architecture unchanged — a routing-table + required-key config change, which **validates the anti-corruption-layer choice**. Cost lever shifts from Anthropic `cache_control` → OpenAI **automatic** prefix caching (read via `cached_tokens`); adaptive thinking → OpenAI reasoning models (deferred hook). Required key flipped `ANTHROPIC_API_KEY` → `OPENAI_API_KEY`. Embeddings (#5) likewise default to OpenAI in S6 unless a Voyage key is added.
