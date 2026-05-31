# Common operations for the AI Travel Planner monorepo.
# All tasks run through uv so they work identically in CI and locally.
# (On Windows without `make`, run the underlying `uv ...` command directly.)

.PHONY: install lint format test test-unit clean

install:            ## Install all workspace packages + dev tools
	uv sync --all-packages

lint:               ## ruff check + mypy (our code only; demo/ is excluded)
	uv run ruff check .
	uv run mypy packages/core/src packages/tools/src

format:             ## auto-format + autofix lint
	uv run ruff format .
	uv run ruff check --fix .

test:               ## all tests
	uv run pytest

test-unit:          ## unit tests only (no running services / network)
	uv run pytest -m "not integration"

clean:              ## remove caches
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -not -path "./old/*" -exec rm -rf {} + 2>/dev/null || true
