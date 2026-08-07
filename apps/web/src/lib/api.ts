/**
 * Server-side backend client. Runs only in BFF route handlers / server
 * components — never in the browser — so the Auth0 access token stays server-side.
 * The browser hits our same-origin /api/* routes, which call these functions.
 */
import "server-only";

import { backendAuthHeader } from "@/lib/auth0";
import type { PlanRequest, RunAccepted, RunRecord, TripRequest } from "@/lib/types";

export function backendUrl(path: string): string {
  const base = process.env.BACKEND_API_URL ?? "http://localhost:8000";
  return `${base.replace(/\/$/, "")}${path}`;
}

/** Map a backend non-2xx into a thrown error carrying its status (for the BFF). */
export class BackendError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "BackendError";
  }
}

async function backendFetch(path: string, init?: RequestInit): Promise<Response> {
  const auth = await backendAuthHeader();
  return fetch(backendUrl(path), {
    ...init,
    headers: {
      "content-type": "application/json",
      ...auth,
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
}

export async function createPlan(body: PlanRequest): Promise<RunAccepted> {
  const res = await backendFetch("/plan", { method: "POST", body: JSON.stringify(body) });
  if (!res.ok) throw new BackendError(res.status, await res.text());
  return (await res.json()) as RunAccepted;
}

export async function createTrip(body: TripRequest): Promise<RunAccepted> {
  const res = await backendFetch("/trip", { method: "POST", body: JSON.stringify(body) });
  if (!res.ok) throw new BackendError(res.status, await res.text());
  return (await res.json()) as RunAccepted;
}

export async function getRun(runId: string): Promise<RunRecord> {
  const res = await backendFetch(`/runs/${encodeURIComponent(runId)}`);
  if (!res.ok) throw new BackendError(res.status, await res.text());
  return (await res.json()) as RunRecord;
}

/** Raw streaming Response from the backend SSE endpoint, for pass-through proxying. */
export async function streamRun(runId: string, signal?: AbortSignal): Promise<Response> {
  const auth = await backendAuthHeader();
  return fetch(backendUrl(`/runs/${encodeURIComponent(runId)}/stream`), {
    headers: { accept: "text/event-stream", ...auth },
    cache: "no-store",
    signal,
  });
}
