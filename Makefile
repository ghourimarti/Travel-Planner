.PHONY: install lint typecheck test check services worker api \
        audit audit-deps sast secrets licenses load chaos \
        data app observability full up ps logs down downv seed migrate bootstrap urls

# ---- Layered local stack: data | app | observability | full ----
# observability  = standalone obs stack (Jaeger/Grafana/Prometheus/Flower/RedisInsight/Langfuse)
# full           = data + app + observability (everything)
DC_DATA := docker compose -f docker-compose.data.yml
DC_APP  := docker compose -f docker-compose.data.yml -f docker-compose.app.yml
DC_OBS  := docker compose -f docker-compose.observability.yml
DC_FULL := docker compose -f docker-compose.data.yml -f docker-compose.app.yml -f docker-compose.observability.yml

install:        ## Sync the uv workspace (all packages + dev tools)
	uv sync

lint:           ## Ruff lint
	uv run ruff check .

typecheck:      ## mypy (strict) on package source
	uv run mypy packages/core/src packages/tools/src packages/agents/src apps/api/src apps/worker/src packages/eval/src packages/retrieval/src

test:           ## Run the test suite
	uv run pytest

check: lint typecheck test   ## Lint + type-check + test (the green gate)

# ---- Phase 5 hardening: audits (run with `uv sync --group audit` first) ----
audit-deps:     ## Supply-chain CVE audit (Python + web prod deps)
	uv run --group audit pip-audit
	pnpm --dir apps/web audit --prod

sast:           ## Static security analysis on first-party source (Bandit)
	uv run --group audit bandit -c pyproject.toml -r packages apps/api apps/worker -q

secrets:        ## Fail on any secret not already in the reviewed baseline
	uv run --group audit detect-secrets-hook --baseline .secrets.baseline $$(git ls-files)

licenses:       ## Print dependency licenses; fail on GPL/AGPL/LGPL/SSPL
	uv run --group audit pip-licenses --fail-on="GPL;AGPL;LGPL;SSPL" --order=license

audit: audit-deps sast licenses   ## Full security/supply-chain audit pass

load:           ## k6 load test against $(BASE_URL) (default http://localhost:8000)
	BASE_URL=$(or $(BASE_URL),http://localhost:8000) k6 run tests/load/plan_smoke.js

chaos:          ## Resilience/chaos tests (kill LLM / Redis / Qdrant, assert graceful degradation)
	uv run pytest -m chaos -v

ingest:         ## Ingest the seed POI corpus into Qdrant (needs OPENAI_API_KEY for embeddings)
	uv run python -m tp_retrieval.ingest

eval:           ## Run the eval harness on fixtures (needs OPENAI_API_KEY; LLM calls cost ~cents)
	uv run python -m tp_eval --judge gateway

eval-rag:       ## Run eval through real retrieval (run `make ingest` first)
	uv run python -m tp_eval --judge gateway --retrieve

# ---- Native dev (run api/worker on the host against the data layer) ----
worker:         ## Run a Celery worker on the host (needs `make data`)
	uv run celery -A tp_worker.celery_app worker -l info

api:            ## Run the API with reload on the host (needs `make data`)
	uv run uvicorn tp_api.main:app --reload

# ---- Containerized stack — four tiers, each overlays the previous ----
data:           ## tier 1: DATA stores only — Postgres + Redis + Qdrant
	$(DC_DATA) up -d

services: data  ## Alias for `data` (backwards-compatible name)

app:            ## tier 2: data + APP (api, worker, web)
	$(DC_APP) up --build -d

observability:  ## obs only: Jaeger/Grafana/Prometheus/Flower/RedisInsight/Langfuse (standalone)
	$(DC_OBS) up -d
	@echo ""
	@$(MAKE) --no-print-directory urls

full:           ## everything: data + app + observability (the full stack)
	$(DC_FULL) up --build -d
	@echo ""
	@$(MAKE) --no-print-directory urls

up: observability   ## Alias for `observability` (backwards-compatible)

seed:           ## Ingest the POI corpus into the running Qdrant server (run after a tier is up)
	set -a; . ./.env 2>/dev/null || true; set +a; \
	QDRANT_URL=http://localhost:$${QDRANT_PORT:-3003} VOYAGE_API_KEY= uv run python -m tp_retrieval.ingest

migrate:        ## Create/upgrade the Postgres schema (idempotent create_all; needs the app tier up)
	# Runs inside the api container: it has the asyncpg driver and the in-network DB URL.
	# (The api also runs this on boot; this target makes the step explicit + re-runnable.)
	$(DC_APP) exec -T api python -c "import asyncio; from tp_core.db import init_models; asyncio.run(init_models())"

bootstrap:      ## FROM SCRATCH in one shot: stores up + DB schema + app, then seed the corpus
	$(DC_APP) up --build -d --wait
	@$(MAKE) --no-print-directory migrate
	@$(MAKE) --no-print-directory seed
	@echo ""
	@echo "  Bootstrap complete - schema created, corpus ingested, app running."
	@echo "  (Run 'make full' to add the observability dashboards.)"
	@$(MAKE) --no-print-directory urls

ps:             ## Status of every container in the stack
	$(DC_FULL) ps

logs:           ## Tail logs for the whole stack (Ctrl-C to stop)
	$(DC_FULL) logs -f --tail=100

down:           ## Stop the stack (keeps data volumes)
	$(DC_FULL) down

downv:          ## Stop the stack AND wipe all data volumes
	$(DC_FULL) down -v

urls:           ## Print which URL opens which UI (ports come from .env)
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	echo ""; \
	echo "  Voyantra - local URLs   (ports are sequenced by startup order in .env)"; \
	echo "  ---------------------------------------------------------------------"; \
	echo "  -- data tier (starts 1st) ----"; \
	echo "  Postgres             localhost:$${POSTGRES_PORT:-3001}            (DB client; user/pass=$${POSTGRES_USER:-tp})"; \
	echo "  Redis                localhost:$${REDIS_PORT:-3002}            (RedisInsight or redis-cli)"; \
	echo "  Qdrant dashboard     http://localhost:$${QDRANT_PORT:-3003}/dashboard"; \
	echo "  Overpass (POIs)      http://localhost:$${OVERPASS_PORT:-3015}/api/status            (first start imports the OSM extract, ~2-4h)"; \
	echo "  -- app tier (starts 2nd) ----"; \
	echo "  API docs (Swagger)   http://localhost:$${API_PORT:-3004}/docs"; \
	echo "  API metrics (raw)    http://localhost:$${API_PORT:-3004}/metrics"; \
	echo "  App (Next.js)        http://localhost:$${WEB_PORT:-3006}            login: $${DEV_LOGIN_PASSWORD:-voyantra}"; \
	echo "  -- observability tier (starts 3rd) ----"; \
	echo "  Jaeger  (traces)     http://localhost:$${JAEGER_UI_PORT:-3007}            service: tp-worker"; \
	echo "  Prometheus           http://localhost:$${PROMETHEUS_PORT:-3009}            Status > Targets"; \
	echo "  Grafana (metrics)    http://localhost:$${GRAFANA_PORT:-3010}            anonymous admin"; \
	echo "  Flower  (Celery)     http://localhost:$${FLOWER_PORT:-3011}"; \
	echo "  RedisInsight         http://localhost:$${REDISINSIGHT_PORT:-3012}            add host=redis port=6379"; \
	echo "  Langfuse (LLM trace) http://localhost:$${LANGFUSE_PORT:-3013}            (make observability or make full)"; \
	echo "  MinIO console        http://localhost:$${MINIO_CONSOLE_PORT:-3014}"; \
	echo "  ---------------------------------------------------------------------"; \
	echo ""
	@echo ""
