# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Toolchain

- **Python**: managed with `uv` (workspace monorepo). Root `pyproject.toml` defines workspace members: `apps/api`, `packages/prompts`, `packages/eval`.
- **Node**: `apps/web` uses `pnpm` (Next.js 15, React 19).
- **All common operations go through the root `Makefile`** — do not run `uv run` or `pnpm` directly unless the Makefile doesn't cover the case.

## Common Commands

```bash
make install              # Install all Python + Node deps
make up                   # Start local stack (postgres + redis + api; web/observability behind profiles)
make down                 # Tear down stack
make seed                 # Ingest data/anime_with_synopsis.csv into pgvector

make test                 # All pytest tests
make test-unit            # Unit tests only (no running stack needed)
make test-integration     # Requires running stack

make lint                 # ruff check + mypy
make format               # ruff format (line-length=100, py311 target)

make alembic-upgrade              # Apply DB migrations
make alembic-revision MSG="..."   # Create new migration

make eval                 # RAGAS offline evaluation
make promptfoo            # Prompt regression tests
make drift-check          # Detect embedding drift
make load-test-smoke      # 1 VU, 30s k6 sanity check
make load-test            # Full k6 ramp with SLO thresholds

make kill-switch-on / kill-switch-off   # Force cheap model globally
make cost-summary                       # Show per-user spend from Redis
make trivy-scan-api / trivy-fs          # Container + filesystem security scan
make tf-plan / helm-lint                # IaC validation (no apply)
```

**Running a single test:**
```bash
cd apps/api && uv run pytest tests/unit/test_rrf.py -v
```

Pytest is configured with `asyncio_mode = "auto"` — no explicit `@pytest.mark.asyncio` needed.

## Architecture

### Request Flow

```
Next.js (SSE) → FastAPI middleware stack → RAGPipeline (LangGraph) → SSE response
```

**Middleware order** (matters for correctness):
1. Security headers
2. `RequestContextMiddleware` — binds `request_id` to structlog context
3. `CORSMiddleware`
4. SlowAPI rate limiter (Redis-backed, 30 req/min per IP by default)

JWT auth (`verify_clerk_token` dependency) is on individual routes, not global middleware. Dev bypass: leave `CLERK_JWKS_URL` empty.

### LangGraph Pipeline

```
cache_check ──hit──► stream cached answer word-by-word ──► END
    │ miss
    ▼
rewrite → retrieve → grade → generate → cache_write → END
```

`run_stream()` bypasses LangGraph's `astream` to emit fine-grained SSE event types: `step`, `token`, `done`. This lets the frontend stream individual tokens rather than full node outputs. The node callables are stored as instance attributes so they can be called directly in the streaming path.

If the rewriter returns the same query unchanged, the embedding computed during `cache_check` is reused — no redundant API call.

### Hybrid Retrieval

Dense and sparse retrieval run concurrently against the same Postgres instance:

- **Dense**: pgvector HNSW cosine (`embedding <=> query_vec::vector`), `text-embedding-3-large` 1536 dims
- **Sparse**: Postgres `tsvector` / `ts_rank_cd()` BM25, GIN index, `plainto_tsquery('english', ...)`
- **Fusion**: RRF with k=60 (`1 / (k + rank)` summed across both lists)
- **Reranking**: Cohere `rerank-english-v3.0` cross-encoder; falls back to RRF order if Cohere is unavailable or key not set

Settings: `top_k=20` candidates from each retriever → RRF merge → Cohere rerank to `rerank_top_n=5`.

### Semantic Cache

Redis cache keyed by **query embedding similarity**, not exact text match. Threshold: cosine ≥ 0.92 = hit. Handles paraphrased queries. Populated by `cache_write` node at pipeline end; TTL is configurable.

### Cost Controls (`core/cost_control.py`)

Three mechanisms, all Redis-backed:
1. **KillSwitch** — forces all LiteLLM calls to `cheap_model` (Haiku) regardless of query complexity
2. **ModelRouter** — routes simple queries (word_count ≤ threshold) to `cheap_model`, complex to `default_model` (Sonnet)
3. **BudgetGuard** — per-user and global daily USD spend caps; resets at midnight UTC

Fallback chain: `default_model` → `fallback_model` (Groq Llama) on exception.

### PII & Guardrails

- **Presidio** (`core/pii.py`): scrubs user query **before embedding** — PERSON, EMAIL, PHONE, CREDIT_CARD, IBAN, IP, SSN, PASSPORT. LOCATION deliberately excluded (too many false positives in anime queries).
- **Guardrails AI** (`core/guardrails.py`): validates LLM output to block injection/jailbreak content.

### Observability

Every query emits to three sinks simultaneously:
- **Langfuse**: end-to-end LLM traces via LiteLLM callback; `trace_id` threaded through `RAGState` → LiteLLM metadata
- **Prometheus**: `rag_tokens_total`, `rag_cost_usd_total`, `rag_retrieval_duration_seconds`, `rag_retrieved_docs_count`
- **Postgres `AuditLog`**: `request_id`, `user_id`, `query_hash`, model, tokens, cost, `cached` flag

### Docker Compose Profiles

Core local stack (no profile flag needed): `postgres`, `redis`, `api`.

Optional via `--profile`:
- `web` — Next.js frontend
- `observability` — Langfuse, Prometheus, Grafana
- `pgbouncer` — transaction-mode connection pool (200 client → 20 server)

### Infrastructure

- **Terraform + Terragrunt**: modules in `infra/terraform/modules/` (networking, ecr, iam, rds, elasticache, eks). `mock_outputs` enables `make tf-plan` without live AWS creds.
- **Helm / Argo Rollouts**: `rollout.yaml` renders as `Rollout` (canary 20→50→100%) when `Values.rollout.enabled=true`, plain `Deployment` otherwise.
- **ArgoCD**: app-of-apps watching `infra/argocd/apps/`. Dev = auto-sync; prod = manual sync only.

## Key Settings

All config lives in `apps/api/src/anime_rag/core/settings.py` (Pydantic `BaseSettings`, `lru_cache`). Copy `.env.example` → `.env`:

- `OPENAI_API_KEY` — required for embeddings
- `ANTHROPIC_API_KEY` or `GROQ_API_KEY` — generation
- `COHERE_API_KEY` — reranking (optional; degrades gracefully)
- `CLERK_JWKS_URL` — leave empty to bypass auth in dev
- Postgres + Redis vars are pre-filled for the local Docker Compose stack

## Database

Schema initialized by `scripts/init_db.sql` (pgvector extension, HNSW index, GIN index for FTS). SQLAlchemy models in `apps/api/src/anime_rag/models/`. Migrations via Alembic in `apps/api/alembic/`.

Ingestion script (`scripts/ingest.py`) reads `data/anime_with_synopsis.csv` (269 MAL titles), embeds synopses, and bulk-upserts into `anime_documents` via psycopg3. Run with `make seed`.
