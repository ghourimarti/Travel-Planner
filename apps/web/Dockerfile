# syntax=docker/dockerfile:1
# voyantra-web — Next.js BFF + product UI (Decision 8 + Decision 15).
# Context = ./apps/web (its own JS root; not part of the uv workspace).
# Stages: deps (pnpm install) -> build (next build, standalone) -> slim runtime.

FROM node:22-slim AS base
ENV PNPM_HOME=/pnpm PATH="/pnpm:$PATH" NEXT_TELEMETRY_DISABLED=1
RUN corepack enable

# ---- deps: install from the frozen lockfile (cached on lockfile changes) ----
FROM base AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile

# ---- build: compile the standalone server ----------------------------------
FROM base AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

# ---- runtime: non-root node serving the standalone output ------------------
FROM node:22-slim AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
WORKDIR /app
RUN useradd --create-home --uid 10001 app
# Standalone bundles the traced server + its node_modules; static assets are copied separately.
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static
USER app

EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD node -e "require('http').get('http://localhost:3000/',r=>process.exit(r.statusCode<500?0:1)).on('error',()=>process.exit(1))"
CMD ["node", "server.js"]
