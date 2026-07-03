"use client";

import { ArrowLeft, ChevronDown, ChevronUp, Sparkles } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { ItineraryView } from "@/components/app/itinerary-view";
import { MapView } from "@/components/app/map-view";
import { TraceTimeline } from "@/components/app/trace-timeline";
import { Button } from "@/components/ui/button";
import { useRunStream } from "@/hooks/use-run-stream";
import type { RunRecord } from "@/lib/types";

function refineHref(record: RunRecord): string {
  const req = record.request as {
    city?: string;
    cities?: string[];
    interests?: string[];
    days?: number;
  };
  const params = new URLSearchParams();
  params.set("days", String(req.days ?? 3));
  if (req.interests?.length) params.set("interests", req.interests.join(","));
  if (record.kind === "trip") {
    params.set("mode", "multi");
    if (req.cities?.length) params.set("cities", req.cities.join(","));
  } else {
    params.set("mode", "single");
    if (req.city) params.set("city", req.city);
  }
  return `/app/plan?${params.toString()}`;
}

export function RunView({ runId }: { runId: string }) {
  const { status, nodes, record, error } = useRunStream(runId);
  const terminal = status === "succeeded" || status === "failed";
  const [traceOpen, setTraceOpen] = React.useState(false);

  return (
    <div className="mx-auto max-w-4xl">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <Button asChild variant="ghost" size="sm">
          <Link href="/app/trips">
            <ArrowLeft className="size-4" /> Trips
          </Link>
        </Button>
        {terminal && record && (
          <Button asChild variant="gradient" size="sm">
            <Link href={refineHref(record)}>
              <Sparkles className="size-4" /> Refine this trip
            </Link>
          </Button>
        )}
      </div>

      {/* While planning: show trace as the primary progress UI */}
      {!terminal && (
        <div className="mb-6 lg:w-96 mx-auto">
          <TraceTimeline nodes={nodes} status={status} />
          {error && (
            <p className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
              {error}
            </p>
          )}
          <div className="mt-6 space-y-3">
            <div className="h-10 animate-pulse rounded-xl border border-border bg-muted/40" />
            <div className="h-48 animate-pulse rounded-xl border border-border bg-muted/40" />
            <div className="h-32 animate-pulse rounded-xl border border-border bg-muted/40" />
          </div>
        </div>
      )}

      {/* Once complete: full-width itinerary, trace collapses to disclosure */}
      {terminal && record && (
        <div className="space-y-6">
          <MapView record={record} />
          <ItineraryView record={record} />

          {/* "How it was planned" — collapsed by default */}
          <div className="rounded-2xl border border-border bg-card">
            <button
              onClick={() => setTraceOpen((o) => !o)}
              className="flex w-full items-center justify-between px-6 py-4 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              <span>How this itinerary was built</span>
              {traceOpen ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
            </button>
            {traceOpen && (
              <div className="border-t border-border px-6 pb-6 pt-4">
                <TraceTimeline nodes={nodes} status={status} />
              </div>
            )}
          </div>
        </div>
      )}

      {terminal && !record && error && (
        <p className="rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}
