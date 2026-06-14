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
apps/api/           # tp_api: FastAPI — async dispatch (POST /plan,/trip -> run_id; GET /runs/{id})
apps/worker/        # tp_worker: Celery worker that runs the planner graph (S9)
packages/retrieval/ # tp_retrieval: embeddings + Qdrant + hybrid retrieve/rerank
packages/eval/      # tp_eval: RAGAS + agent-trajectory eval harness
apps/ · packages/   # web · ingestion                 (added in later steps)
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

## Run the API + worker (S9 — async dispatch)

`POST /plan` and `/trip` no longer block: they persist a run, enqueue a Celery task,
and return a `run_id`. The graph executes on the worker; poll `GET /runs/{id}` for
status + result.

```bash
make services                 # Postgres + Redis via Docker (or omit DATABASE_URL for no-Docker sqlite)
make worker                   # shell 2: Celery worker (runs the planner graph)
make api                      # shell 3: uvicorn on :8000

curl localhost:8000/health
RID=$(curl -s -X POST localhost:8000/plan -H "content-type: application/json" \
  -d '{"city":"Kyoto","interests":["temples"],"days":1}' | jq -r .run_id)
curl -s localhost:8000/runs/$RID            # -> {"status":"running"|"succeeded", "result": {...}}

# multi-city (S8): parallel per-city workers + inter-city legs + partial results
curl -s -X POST localhost:8000/trip -H "content-type: application/json" \
  -d '{"cities":["Tokyo","Kyoto"],"interests":["temples","food"],"days":4}'
```

The worker runs the multi-agent LangGraph (coordinator → per-city worker [geocode →
gather POIs + weather → compose] → critic → corrective loop), grounds the itinerary in
real places, and records status/result/cost on the run. The LangGraph Postgres
checkpointer (resume-after-crash) and SSE progress streaming land in S9b/S9c.

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
