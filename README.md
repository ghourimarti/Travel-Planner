# AI Travel Planner — Agentic RAG (production transformation)

A multi-agent, multi-city travel planner that grounds itineraries in real POIs,
weather, and routing. Built as a `uv` monorepo and transformed from a portfolio
demo to a production-grade service. See [`docs/architecture-decision-log.md`](docs/architecture-decision-log.md)
for the 22 architecture decisions and [`docs/decision-summary.md`](docs/decision-summary.md)
for the at-a-glance matrix.

## Layout

```
packages/core/      # tp_core: typed config, JSON logging, exceptions
apps/               # api · worker · ingestion · web   (added in later steps)
packages/           # agents · tools · retrieval · eval (added in later steps)
infra/ · docs/      # IaC + decision records
demo/               # original Streamlit portfolio app (legacy; being strangled)
```

## Quickstart

```bash
uv sync                       # create the env + install all workspace packages
cp .env.example .env          # then fill in ANTHROPIC_API_KEY (required)

make check                    # lint + type-check + test   (or run individually:)
uv run ruff check .
uv run mypy packages/core/src
uv run pytest
```

Requires Python 3.13 (pinned in `.python-version`) and [`uv`](https://docs.astral.sh/uv/).
`make` is optional on Windows — the raw `uv run ...` commands above are equivalent.
