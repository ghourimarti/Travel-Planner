.PHONY: install lint typecheck test check services worker api

install:        ## Sync the uv workspace (all packages + dev tools)
	uv sync

lint:           ## Ruff lint
	uv run ruff check .

typecheck:      ## mypy (strict) on package source
	uv run mypy packages/core/src packages/tools/src packages/agents/src apps/api/src apps/worker/src packages/eval/src packages/retrieval/src

test:           ## Run the test suite
	uv run pytest

check: lint typecheck test   ## Lint + type-check + test (the green gate)

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
