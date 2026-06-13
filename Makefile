.PHONY: install lint typecheck test check

install:        ## Sync the uv workspace (all packages + dev tools)
	uv sync

lint:           ## Ruff lint
	uv run ruff check .

typecheck:      ## mypy (strict) on package source
	uv run mypy packages/core/src packages/tools/src packages/agents/src apps/api/src packages/eval/src

test:           ## Run the test suite
	uv run pytest

check: lint typecheck test   ## Lint + type-check + test (the green gate)

eval:           ## Run the eval harness (needs OPENAI_API_KEY; LLM calls cost ~cents)
	uv run python -m tp_eval --judge gateway
