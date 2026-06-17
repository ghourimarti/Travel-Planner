"use client";

import { Check, Loader2 } from "lucide-react";

import type { NodePhase } from "@/hooks/use-run-stream";
import { AGENT_NODES, NODE_LABELS, type RunStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

export function TraceTimeline({
  nodes,
  status,
}: {
  nodes: Record<string, NodePhase>;
  status: RunStatus | "connecting";
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-6">
      <div className="flex items-center justify-between border-b border-border pb-4">
        <h2 className="font-semibold">Agent trace</h2>
        <StatusPill status={status} />
      </div>
      <ol className="mt-5 space-y-3">
        {AGENT_NODES.map((node) => {
          const phase = nodes[node] ?? "pending";
          const meta = NODE_LABELS[node];
          return (
            <li
              key={node}
              className={cn(
                "flex items-start gap-3 rounded-xl border px-4 py-3 transition-all",
                phase === "done" && "border-emerald-500/30 bg-emerald-500/5",
                phase === "running" && "border-primary/40 bg-primary/5",
                phase === "pending" && "border-border opacity-60",
              )}
            >
              <span
                className={cn(
                  "mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-medium",
                  phase === "done" && "bg-emerald-500/15 text-emerald-500",
                  phase === "running" && "bg-primary/15 text-primary",
                  phase === "pending" && "bg-muted text-muted-foreground",
                )}
              >
                {phase === "done" ? (
                  <Check className="size-4" />
                ) : phase === "running" ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  AGENT_NODES.indexOf(node) + 1
                )}
              </span>
              <div>
                <p className="text-sm font-medium">{meta.title}</p>
                <p className="text-xs text-muted-foreground">{meta.blurb}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function StatusPill({ status }: { status: RunStatus | "connecting" }) {
  const map: Record<string, { label: string; cls: string }> = {
    connecting: { label: "Connecting", cls: "bg-muted text-muted-foreground" },
    queued: { label: "Queued", cls: "bg-muted text-muted-foreground" },
    running: { label: "Running", cls: "bg-primary/15 text-primary" },
    succeeded: { label: "Complete", cls: "bg-emerald-500/15 text-emerald-500" },
    failed: { label: "Failed", cls: "bg-red-500/15 text-red-500" },
  };
  const s = map[status] ?? map.connecting;
  return <span className={cn("rounded-full px-2.5 py-1 text-xs font-medium", s.cls)}>{s.label}</span>;
}
