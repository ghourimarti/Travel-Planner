.PHONY: install lint typecheck test check services worker api \
        audit audit-deps sast secrets licenses load chaos

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

services:       ## Start local backing services (Postgres + Redis)
	docker compose up -d

worker:         ## Run a Celery worker (needs `make services`)
	uv run celery -A tp_worker.celery_app worker -l info

api:            ## Run the API with reload (needs `make services`)
	uv run uvicorn tp_api.main:app --reload
