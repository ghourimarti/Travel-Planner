# Voyantra Web (`apps/web`)

The enterprise marketing site **and** product app for the AI Travel Planner — a
Next.js 15 (App Router) frontend that talks to the FastAPI backend through a
**BFF** (server-side route handlers), so Auth0 access tokens never reach the
browser. Implements transformation step **S13**.

## Stack
- Next.js 15 (App Router, React 19) · TypeScript (strict)
- Tailwind CSS v4 + hand-authored shadcn-style primitives (Radix)
- Auth0 (`@auth0/nextjs-auth0` v4) — **optional**: the app runs keyless in dev
- Vitest + Testing Library (hermetic; no backend/Auth0 needed)

## Run it locally
```bash
pnpm install
cp .env.example .env.local        # optional — fill the Auth0 block for real login
pnpm dev                          # http://localhost:3000
```
The product app lives at `/app`. With no Auth0 env set and the backend in dev
mode (`AUTH_REQUIRED=false`), `/app` is open and the full trace UI works against
`http://localhost:8000`.

Point at a different backend with `BACKEND_API_URL`.

## Quality gate
```bash
pnpm lint          # ESLint (next/core-web-vitals)
pnpm typecheck     # tsc --noEmit
pnpm test          # Vitest (api client, useRunStream, TraceTimeline, utils)
pnpm build         # production build
```

## Architecture
- `src/app/(marketing)/*` — public site (home, features, pricing, enterprise, about, contact, legal)
- `src/app/app/*` — Auth0-protected product (dashboard, plan, live run, trips)
- `src/app/api/*` — BFF proxies to FastAPI (`/plan`, `/trip`, `/runs/:id`, `/runs/:id/stream` SSE pass-through)
- `src/lib/types.ts` — TypeScript mirror of the backend Pydantic contract
- `src/hooks/use-run-stream.ts` — same-origin SSE → per-node trace state
