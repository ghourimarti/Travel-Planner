# syntax=docker/dockerfile:1
# tp-api — FastAPI dispatch surface. Multi-stage uv build (Decision 15):
#   builder  installs the workspace venv with uv (build tools stay here)
#   runtime  slim + non-root, carries only the venv + source
# Context = repo root (the uv workspace needs all members to resolve the lock).

# ---- builder ---------------------------------------------------------------
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app

# Only the manifests + lock first → this layer caches across source-only changes.
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

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"
CMD ["uvicorn", "tp_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
