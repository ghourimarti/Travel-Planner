# Architecture Decision Log — AI Travel Planner (Production Transformation)

> **Project:** P3-AI-Travel-Planner — transforming a portfolio-grade Streamlit demo into a production-grade **Agentic AI** application.
> **Status:** Phase 2 LOCKED (2026-05-31). 22 decisions ratified; D2/D3/D4 reflect user overrides.
> **Source of truth:** Career Assessment, Market Positioning, and Service Packages Build-Spec (Package 2 — Agentic AI).
> **Scale targets it must respect:** see NFRs below.

---

## Phase 0 — Mapping
Target service package: **Package 2 — Production-grade Agentic AI** (user-confirmed). The current `demo/` is a single-shot Streamlit + ChatGroq itinerary generator; the target is a multi-agent, tool-using, observable, cost-controlled travel planner.

## Phase 1 — Non-Functional Requirements (locked defaults)
- **Latency:** Time-to-first-step < 1.5 s; full run p50 ≤ 12 s, p95 ≤ 25 s, p99 ≤ 40 s; hard timeout 60 s.
- **Scale:** design ceiling 1M MAU / ~30k DAU / peak ~300 concurrent; **validated target = 50 concurrent runs** (k6).
- **Availability:** SLO 99.5% validated / design-for 99.9%. SLI = successful itinerary generations / valid requests (4xx excluded; graceful partials = success).
- **Cost:** target < $0.10/itinerary; hard caps per run: $0.25 + kill-switch, 8 steps, ~40k tokens; per-user + global daily budget guard.
- **Compliance:** GDPR-aware (data minimization, deletion path, PII scrub). No HIPAA/PCI/SOC2 in v1.
- **Auth:** anonymous + IP rate-limit in v1; accounts (Clerk) as designed-for stretch.
- **Residency:** single region, region-pinnable. Multi-region out of scope.
- **Functional scope:** destination + interests (+1–3 days, default 1) → grounded, time-sequenced, cited itinerary via tools (POI, weather, geo/routing). One-shot v1; refinement as stretch.
- **Out of scope:** real bookings/payments, multi-region active-active, native mobile, social/UGC, billing, custom fine-tuning, voice.

---

## The 22 Decisions

### Decision 1: Primary Database
**Question:** System of record for run state, step logs, tool-call audit, itineraries, users?
**Decision:** **PostgreSQL** (Docker → AWS RDS). Primary relational store; the `pgvector` role is dropped because vectors live in Pinecone (D2).
**Reasoning:** Relational + JSONB serves audit/run-state/users; lean transactional DB without HNSW tuning.
**Trade-offs:** Two data stores now (Postgres + Pinecone) instead of one.
**Reversibility:** Moderate. Revisit: extreme write scale → partition.

### Decision 2: Vector Database
**Question:** Where do embeddings live (agent memory + future corpus)?
**Options:** A pgvector | B Qdrant | **C Pinecone (managed) ✓**
**Decision:** **Pinecone (serverless)**, index dim 1536 (matches D5). Agent long-term memory + any future corpus. Semantic cache stays in Redis (D10).
**Reasoning:** Zero-ops managed vectors; offloads scaling/replication for a solo operator; closes "managed vector-DB ops" skill line; keeps Postgres lean. *(User override.)*
**Trade-offs:** Non-AWS dependency (data egress out of region), lock-in, usage cost, two data systems.
**Reversibility:** Easy–Moderate (behind a `Retriever` interface). Revisit: cost/residency → Qdrant self-host.
**Cascades:** D14 (egress/residency note), D18 (no PII into Pinecone + DPA line).

### Decision 3: Agent Architecture
**Question:** Single vs multi-agent; orchestration pattern?
**Options:** A single graph | B single ReAct | **C multi-agent (planner+researcher+writer) ✓**
**Decision:** **Multi-agent on LangGraph (supervisor/orchestrator-worker):** Orchestrator (routing + global caps), Planner (decompose into research plan), Researcher (only tool-using agent: POI/weather/routing), Writer (synthesize grounded cited itinerary).
**Reasoning:** Higher-ceiling, clean separation; closes the multi-agent orchestration gap; strong portfolio signal. *(User override.)*
**Trade-offs:** More LLM calls (≈6–12/run) → pressures p95 ≤ 25s and < $0.10/run. **Mitigations:** Groq-first latency (D4), parallel researcher tool calls, global step/cost caps (D20), caching (D10).
**Reversibility:** Moderate. Revisit: NFR breach in eval/load → collapse planner into orchestrator, or single-agent.
**Cascades:** D11 (longer runs → queue trigger closer), D19 (per-agent + e2e eval), D22 (agent package holds 4 agents).

### Decision 4: LLM Provider & Tiering
**Question:** Provider order, tiering, fallback chain?
**Options:** A Anthropic-first | B OpenAI-first | **C Groq-first ✓**
**Decision:** **LiteLLM chain: Groq → OpenAI → Anthropic (last).** Tiered: routine = Groq `llama-3.1-8b-instant`; default = Groq `llama-3.3-70b-versatile`; fallback = OpenAI (`gpt-4o-mini`/`gpt-4o`) → Anthropic (`Haiku`/`Sonnet`). Confidence-based escalation up the chain on validation failure.
**Reasoning:** Cheapest + fastest first; Groq latency offsets multi-agent round-trips (synergy with D3); graded fallbacks preserve resilience. *(User override.)*
**Trade-offs:** Open-weight-first → weaker complex planning; mitigated by confidence-based escalation.
**Reversibility:** Easy (LiteLLM config). Revisit: planning quality shortfall → promote stronger default.
**Cascades:** D20 (lowers per-call cost, offsets D3 call count).

### Decision 5: Embedding Model
**Decision:** **OpenAI `text-embedding-3-small` (1536)**, no fine-tuning, versioned.
**Reasoning:** Cheap, sufficient for cache/memory, fits Pinecone index dim.
**Trade-offs:** Lower recall than `-large`; negligible for cache. **Reversibility:** Moderate (re-embed). Revisit: multilingual corpus → e5.

### Decision 6: Orchestration Framework
**Decision:** **LangGraph** (multi-agent supervisor graph) + plain Pydantic-typed tool functions.
**Reasoning:** Explicit state, checkpointing, HITL, step streaming; supports supervisor pattern; in your existing ecosystem. Tools stay framework-free for testability.
**Trade-offs:** LangGraph version churn (contained to the graph layer). **Reversibility:** Moderate.

### Decision 7: Backend Language & Framework
**Decision:** **Python + FastAPI** (async), REST + SSE.
**Reasoning:** AI stack is Python; async fits long IO-bound runs + token/step streaming; Pydantic v2 typed boundaries. SSE (one-directional) over WebSocket.
**Trade-offs:** Python GIL (non-issue, IO-bound). **Reversibility:** Hard (core).

### Decision 8: Frontend & Streaming UX
**Decision:** **Next.js (App Router, TS) + Tailwind/shadcn**, SSE consumer (`step`/`token`/`done`), agent-trace panel, stop (AbortController) + retry. Streamlit retired (kept only as internal debug harness if useful).
**Reasoning:** Transparency is the product for agents; Streamlit can't do real streaming/auth/trace UX. **Reversibility:** Moderate.

### Decision 9: Authentication & Authorization
**Decision:** **v1 anonymous + SlowAPI IP rate-limit; JWT-verification seam (per-route dependency, dev-bypass) for drop-in Clerk later.**
**Reasoning:** GDPR-minimal, ship fast, additive path to accounts. Per-route dependency = fail-closed where needed.
**Trade-offs:** Anonymous abuse surface (bounded by rate-limit + cost caps). **Reversibility:** Easy. Revisit: need accounts/quotas → Clerk.

### Decision 10: Caching Strategy
**Decision:** **Layered Redis:** semantic itinerary cache (embedding of normalized `city+sorted interests+days`, cosine ≥ 0.92, TTL 6–24h); tool-result cache (POI ~7d, weather ~1h); embedding cache; Anthropic prompt caching for the static system prompt. Invalidation = TTL + prompt-version key.
**Reasoning:** Biggest cost/latency lever; weather volatility handled by caching tool results separately from the final plan. **Reversibility:** Easy.

### Decision 11: Queue & Async Work
**Options:** **A inline async + SSE + Postgres checkpoint ✓** | B worker+queue | C synchronous
**Decision:** **Inline async run + SSE streaming + LangGraph checkpoint to Postgres**, with a documented seam to queue+workers (KEDA on EKS).
**Reasoning:** Adequate + far simpler at validated 50 concurrent × 60s; checkpoint gives partial durability; seam keeps the ceiling reachable. *(Divergence from build-spec workers default.)*
**Trade-offs:** Dropped connection ends the live stream (state persists; a resume endpoint can recover). **Reversibility:** Moderate. Revisit: >100 concurrent / survive-disconnect / batch → workers.

### Decision 12: Inference Serving
**Decision:** **Hosted APIs via LiteLLM. No self-hosted GPU in v1.** Document where vLLM would plug in.
**Reasoning:** Bursty low-volume → hosted wins on cost + ops; no idle-GPU waste. **Reversibility:** Easy. Revisit: high steady QPS on open-weight → vLLM.

### Decision 13: Observability Stack
**Decision:** **Langfuse (LLM traces/cost) + Prometheus + Grafana (metrics/SLO/alerts) + OpenTelemetry (app traces) + structlog → existing ELK/Filebeat (log aggregation).** Trace every run: per-step, tool calls, tokens, cost, latency-per-stage, correlated `trace_id`. Alert on SLO burn, cost spike, tool-error spike, runaway runs. Local: only Langfuse+Prometheus required; ELK behind a compose profile.
**Reasoning:** Agents fail silently + expensively → highest-leverage Package 2 investment; reuses existing ELK. **Reversibility:** Moderate.

### Decision 14: Cloud Provider & Core Services
**Decision:** **AWS, us-east-1** (region-pinnable): EKS, RDS, ElastiCache, S3, Secrets Manager, ECR, ALB, Route53, CloudWatch.
**Reasoning:** Builds the AWS-depth gap deliberately; managed services reduce solo ops. GDPR satisfied via data-minimization (anonymous). **Note:** Pinecone (D2) adds non-AWS data egress. **Reversibility:** Hard. Revisit: significant EU PII → eu-west-1.

### Decision 15: Container, Orchestration & IaC
**Decision:** **Docker (multi-stage, non-root) → AWS EKS** + **Terraform** modules + **Helm** + **Argo Rollouts** (canary) + **ArgoCD** GitOps. Local = minikube/kind.
**Reasoning:** Deliberate learning-weighted pick to close the production-K8s/EKS gap (market-valued); reuses existing K8s+ELK manifests. *Honest flag: ECS Fargate would be simpler for a pure product.*
**Trade-offs:** Real ops overhead + ~$73/mo control plane. **Reversibility:** Hard. Revisit: ops too heavy solo → ECS Fargate.

### Decision 16: CI/CD Pipeline
**Decision:** **GitHub Actions:** lint/type → unit → integration → build → Trivy scan → ECR → ArgoCD staging → **eval gate** → manual promote → smoke → Argo Rollouts canary + auto-rollback. Envs: dev (auto-sync), staging, prod (manual sync).
**Reasoning:** Eval gate blocks silent quality regressions; closes CI/CD + eval gaps. **Reversibility:** Easy. *(User runs all git; CI fires on push.)*

### Decision 17: Secrets & Configuration
**Decision:** **Pydantic `BaseSettings`** (typed, `lru_cache`, per-env) + **AWS Secrets Manager + External Secrets Operator**. **Fix `.gitignore` immediately** (`.env`, `logs/`, `__pycache__`, `.venv`). Rotate any previously-committed `GROQ_API_KEY`.
**Reasoning:** 12-factor; fixes the live `.env` leak finding. **Reversibility:** Easy.

### Decision 18: Security Posture
**Threat model:** prompt injection **via tool output** (untrusted external data), jailbreaks, PII leakage in logs/traces, cost-exhaustion DoS (anonymous), SSRF via tools, exfiltration.
**Decision:** **Presidio** PII scrub before log/persist/embed; **Guardrails AI** on input+output; **treat tool outputs as untrusted** (sanitize before LLM — tools are read-only, so no privileged-action hijack); **tool egress allowlist** (overpass/open-meteo/osrm only — SSRF); rate-limit + cost caps (DoS); secrets never logged; security headers; Trivy scans; fail-closed auth seam; no PII into Pinecone.
**Reasoning:** Agentic-specific risk is injection-through-tool-data, not tool actions (read-only). **Reversibility:** Easy–Moderate.

### Decision 19: Evaluation Strategy
**Decision:** **Offline golden set** `(city, interests, days)` → **deterministic checks** (place-validity via tool, geo-coherent ordering, within open hours, within step/cost budget) **+ LLM-judge rubric** (interest-match, quality); **promptfoo** for prompt regression; **CI eval gate**; **online sampling** in prod (Langfuse). Versioned golden set. Multi-agent: per-agent handoff + end-to-end trajectory.
**Reasoning:** Catches silent regressions; lean on cheap objective checks before subjective judge. **Reversibility:** Easy. Revisit: add RAG tool → add RAGAS.

### Decision 20: Cost Controls
**Decision:** **BudgetGuard** (per-user + global daily USD, midnight-UTC reset), **ModelRouter** (route by query complexity), **KillSwitch** (force cheap model), **hard step(8)/token(40k)/$(0.25) caps** inside the multi-agent loop, cost → Prometheus + Langfuse, alert at 80%.
**Reasoning:** Agents are cost-unbounded by default; mechanically enforces Phase-1 caps. Groq-first (D4) lowers per-call cost, offsetting D3's call count. **Reversibility:** Easy.

### Decision 21: Failure-Mode & Degradation
**Decision:** Explicit degradation matrix + circuit breakers + retries (jittered backoff) + timeouts + graceful partials:
- LLM provider down → LiteLLM fallback (Groq→OpenAI→Anthropic); all down → cached or fail-fast.
- Tool fails/timeout → breaker + retry; open breaker → proceed with partial data, flag the gap.
- POI empty → widen radius/relax filters; last resort = LLM general knowledge marked "unverified."
- Redis down → skip cache, compute directly. Postgres down → fail fast 503.
- Malicious input → guardrail block + safe refusal. Budget exceeded → kill-switch / refuse.
**Reasoning:** Many failure points; graceful partial itinerary is the senior behavior. Proven via Phase-5 chaos tests. **Reversibility:** Easy.

### Decision 22: Repo Structure
**Decision:** **Monorepo** (uv Python workspace + pnpm web + Makefile):
```
travel-agent/
├── apps/{web (Next.js), api (FastAPI)}
├── packages/{agent (orchestrator+planner+researcher+writer, prompts), tools (typed tools+tests), core (schemas, clients, settings, litellm, cost, pii), eval (suites, judges, golden sets)}
├── infra/{terraform, k8s (helm, argo, ELK)}
├── .github/workflows/, tests/, docs/
```
**Reasoning:** Shared Pydantic schemas; one build/test/deploy surface; ~60% reusable baseline across future portfolio projects. **Reversibility:** Hard (one-time foundation).

---

## At-a-Glance Summary

| # | Pick | Prod? | Skill-gap closed (★=major) | Rev. | Diverges? |
|---|---|---|---|---|---|
| 1 | PostgreSQL (RDS) | Y | AWS RDS / data | Mod | No |
| 2 | Pinecone serverless | Y | Managed vector-DB ops | Easy-Mod | **Yes** (Qdrant baseline; non-AWS) |
| 3 | Multi-agent supervisor (LangGraph) | Y | ★ Multi-agent orchestration | Mod | **Yes** (single-agent baseline) |
| 4 | Groq→OpenAI→Anthropic (LiteLLM) | Y | Model routing/fallback | Easy | Partial |
| 5 | text-embedding-3-small (1536) | Y | Embeddings | Mod | No |
| 6 | LangGraph + plain tools | Y | LangGraph / agents | Mod | No |
| 7 | Python FastAPI async, REST+SSE | Y | Async API design | Hard | No |
| 8 | Next.js + SSE + trace UI | Y | Prod frontend / streaming UX | Mod | No |
| 9 | Anon + rate-limit, JWT seam | Y* | AuthN/Z seam | Easy | No |
| 10 | Layered Redis cache | Y | Semantic caching | Easy | No |
| 11 | Inline async + checkpoint, queue seam | Y | Async patterns | Mod | **Yes** (workers baseline) |
| 12 | Hosted via LiteLLM, no GPU | Y | Serving trade-off judgment | Easy | No |
| 13 | Langfuse+Prom+Graf+OTel+ELK | Y | ★ Observability / SLO | Mod | Partial |
| 14 | AWS us-east-1 + managed | Y | ★ AWS depth | Hard | No |
| 15 | EKS+Terraform+Helm+Argo | Y | ★ Production K8s / EKS | Hard | No |
| 16 | GitHub Actions + eval gate + canary | Y | CI/CD depth + eval gate | Easy | No |
| 17 | Pydantic + Secrets Mgr + ESO | Y | Secrets management | Easy | No |
| 18 | Presidio+Guardrails+egress allowlist | Y | ★ AI security/compliance | Easy-Mod | No |
| 19 | Trajectory+judge+promptfoo+gate | Y | ★ Eval frameworks | Easy | Partial |
| 20 | BudgetGuard+Router+KillSwitch+caps | Y | Cost engineering | Easy | No |
| 21 | Degradation matrix + breakers | Y | ★ Reliability / distributed sys | Easy | No |
| 22 | Monorepo (uv+pnpm) | Y | Project structure | Hard | No |

**Major skill-audit gaps closed by this build (★): 8** — multi-agent orchestration, observability/SLO, AWS depth, production K8s, AI security, eval frameworks, reliability/distributed systems, + managed vector-DB ops.

**Deliberate divergences from build-spec baseline:** D2 (Pinecone vs Qdrant — user), D3 (multi-agent vs single — user), D11 (inline vs workers — right-sizing). Each carries a documented revisit trigger.
