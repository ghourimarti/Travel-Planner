"use client";

import * as React from "react";

import { AGENT_NODES, type RunEvent, type RunRecord, type RunStatus } from "@/lib/types";

export type NodePhase = "pending" | "running" | "done";

export interface RunStreamState {
  status: RunStatus | "connecting";
  nodes: Record<string, NodePhase>;
  feed: RunEvent[];
  record: RunRecord | null;
  error: string | null;
}

function initialNodes(): Record<string, NodePhase> {
  return Object.fromEntries(AGENT_NODES.map((n) => [n, "pending"]));
}

function advance(nodes: Record<string, NodePhase>, completed: string): Record<string, NodePhase> {
  const next = { ...nodes };
  if (completed in next) next[completed] = "done";
  const idx = AGENT_NODES.indexOf(completed as (typeof AGENT_NODES)[number]);
  const following = AGENT_NODES[idx + 1];
  if (following && next[following] === "pending") next[following] = "running";
  return next;
}

/**
 * Subscribe to the same-origin SSE stream for a run, fold events into per-node
 * phases, and fetch the final RunRecord (with the itinerary) once the run ends.
 */
export function useRunStream(runId: string): RunStreamState {
  const [state, setState] = React.useState<RunStreamState>({
    status: "connecting",
    nodes: { ...initialNodes(), geocode: "running" },
    feed: [],
    record: null,
    error: null,
  });

  React.useEffect(() => {
    let cancelled = false;
    const source = new EventSource(`/api/runs/${encodeURIComponent(runId)}/stream`);

    async function finalize(status: RunStatus) {
      source.close();
      try {
        const res = await fetch(`/api/runs/${encodeURIComponent(runId)}`, { cache: "no-store" });
        const record = (await res.json()) as RunRecord;
        if (!cancelled) {
          setState((prev) => ({
            ...prev,
            record,
            status: record.status ?? status,
            nodes: Object.fromEntries(Object.keys(prev.nodes).map((k) => [k, "done"])),
          }));
        }
      } catch {
        if (!cancelled) setState((prev) => ({ ...prev, status, error: "failed to load result" }));
      }
    }

    source.onmessage = (e: MessageEvent<string>) => {
      let evt: RunEvent;
      try {
        evt = JSON.parse(e.data) as RunEvent;
      } catch {
        return;
      }
      if (cancelled) return;

      setState((prev) => {
        const next: RunStreamState = { ...prev, feed: [...prev.feed, evt] };
        switch (evt.type) {
          case "status":
            next.status = evt.status;
            break;
          case "node":
            next.status = "running";
            if (evt.node) next.nodes = advance(prev.nodes, evt.node);
            break;
          case "error":
            next.error = evt.detail;
            break;
        }
        return next;
      });

      if (evt.type === "done" || evt.type === "succeeded") void finalize("succeeded");
      if (evt.type === "failed") void finalize("failed");
    };

    source.onerror = () => {
      // The BFF emits one finite stream; on transport error stop retrying and
      // fall back to a one-shot fetch of the final record.
      if (!cancelled && source.readyState === EventSource.CLOSED) void finalize("failed");
    };

    return () => {
      cancelled = true;
      source.close();
    };
  }, [runId]);

  return state;
}
