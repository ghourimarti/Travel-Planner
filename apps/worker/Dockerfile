# syntax=docker/dockerfile:1
# tp-worker — Celery worker running the planner graph off the request thread.
# Same multi-stage uv pattern as the api image; only the entrypoint differs.
# Context = repo root.

# ---- builder ---------------------------------------------------------------
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/ packages/
COPY apps/api/ apps/api/
COPY apps/worker/ apps/worker/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra postgres

# ---- runtime ---------------------------------------------------------------
FROM python:3.13-slim AS runtime
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home --uid 10001 app
COPY --from=builder --chown=app:app /app /app
USER app

# The worker is its own Prometheus scrape target on WORKER_METRICS_PORT (default 9200).
EXPOSE 9200
HEALTHCHECK --interval=15s --timeout=10s --start-period=30s --retries=5 \
  CMD celery -A tp_worker.celery_app inspect ping || exit 1
CMD ["celery", "-A", "tp_worker.celery_app", "worker", "-l", "info"]
