# AI Travel Planner — Production-Grade Agentic AI

A multi-agent, tool-using travel itinerary planner — being transformed **in place** from a
portfolio-grade Streamlit demo into a production-grade agentic AI application.

> **Status:** 🚧 Transformation in progress (Phase 4 — execution).
> Architecture decisions: [`docs/architecture-decision-log.md`](docs/architecture-decision-log.md).

## What it does

Given a destination + interests (+ trip length), a **LangGraph multi-agent system**
(orchestrator → planner → researcher → writer) plans a grounded, time-sequenced, cited
itinerary using real tools (points-of-interest, weather, geo/routing) — not a hallucinated guess.

## Tech (target architecture)

| Layer | Choice |
|---|---|
| Agent | LangGraph multi-agent supervisor |
| LLM | Groq → OpenAI → Anthropic (LiteLLM, tiered + fallback) |
| Backend | Python + FastAPI (async, SSE streaming) |
| Frontend | Next.js (agent-trace + streaming UI) |
| Data | PostgreSQL (state/audit) + Pinecone (vectors) + Redis (cache) |
| Infra | Docker → AWS EKS, Terraform, Helm, Argo Rollouts, ArgoCD |
| Obs | Langfuse + Prometheus + Grafana + OpenTelemetry + ELK |

## Repository layout (monorepo)

```
apps/        web (Next.js), api (FastAPI)          # added in later steps
packages/    core, agent, tools, eval              # core exists now
infra/       terraform, k8s                         # added in later steps
docs/        architecture decision log, runbooks
demo/        legacy Streamlit app (retired at Step 13)
```

## Local development

Python is managed with [`uv`](https://docs.astral.sh/uv/) (workspace) on Python 3.13.

```bash
make install      # uv sync --all-packages  (workspace + dev tools)
make lint         # ruff check + mypy
make test         # pytest
make format       # ruff format + autofix
```

> On Windows without `make`, run the underlying `uv ...` commands directly
> (e.g. `uv sync --all-packages`, `uv run pytest`).

Copy `.env.example` → `.env` and fill in provider keys (at least `GROQ_API_KEY`).
