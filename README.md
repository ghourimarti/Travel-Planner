# AI Travel Planner — Agentic RAG (production transformation)

A multi-agent, multi-city travel planner that grounds itineraries in real POIs,
weather, and routing. Built as a `uv` monorepo and transformed from a portfolio
demo to a production-grade service. See [`docs/architecture-decision-log.md`](docs/architecture-decision-log.md)
for the 22 architecture decisions and [`docs/decision-summary.md`](docs/decision-summary.md)
for the at-a-glance matrix.

## Layout

```
packages/core/      # tp_core: typed config, JSON logging, exceptions, LLM gateway
packages/tools/     # tp_tools: typed geocode/POI/weather/routing tools
packages/agents/    # tp_agents: LangGraph planner (single-agent slice; multi-agent in S7)
apps/api/           # tp_api: FastAPI — POST /plan, GET /health
apps/               # worker · ingestion · web        (added in later steps)
packages/           # retrieval · eval                (added in later steps)
infra/ · docs/      # IaC + decision records
demo/               # original Streamlit portfolio app (legacy; strangled, retired in S13)
```

## Quickstart

```bash
uv sync                       # create the env + install all workspace packages
cp .env.example .env          # then set OPENAI_API_KEY (required); ANTHROPIC_API_KEY / GROQ_API_KEY optional

make check                    # lint + type-check + test   (or run individually:)
uv run ruff check .
uv run mypy packages/core/src packages/tools/src packages/agents/src apps/api/src
uv run pytest
```

## Run the API (S4)

```bash
uv run uvicorn tp_api.main:app --reload --port 8000
# in another shell:
curl localhost:8000/health
curl -X POST localhost:8000/plan -H "content-type: application/json" \
  -d '{"city":"Kyoto","interests":["temples"],"days":1}'
```

`POST /plan` runs the single-agent LangGraph (geocode → gather POIs + weather → compose),
grounds the itinerary in real places, and returns warnings + cost. Multi-agent, multi-city,
and the web UI arrive in later steps.

## Eval & retrieval (S5/S6)

```bash
make ingest    # embed the seed POI corpus (data/corpus/pois.jsonl) into local Qdrant
make eval      # score the planner on fixed fixtures      -> baselines/baseline.json
make eval-rag  # score through real corpus retrieval (S6) -> baselines/baseline-rag.json
```

Embeddings use Voyage if `VOYAGE_API_KEY` is set, else OpenAI `text-embedding-3-large`
(both 1024-d). The embedded Qdrant lives in `.qdrant_local/` (gitignored; rebuild with
`make ingest`). `eval`/`eval-rag` make real LLM calls (~cents) and need `OPENAI_API_KEY`.

Requires Python 3.13 (pinned in `.python-version`) and [`uv`](https://docs.astral.sh/uv/).
`make` is optional on Windows — the raw `uv run ...` commands above are equivalent.
