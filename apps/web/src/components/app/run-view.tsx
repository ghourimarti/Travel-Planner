"use client";

import { ArrowLeft, RefreshCw, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ItineraryView } from "@/components/app/itinerary-view";
import { MapView } from "@/components/app/map-view";
import { TraceTimeline } from "@/components/app/trace-timeline";
import { Button } from "@/components/ui/button";
import { useRunStream } from "@/hooks/use-run-stream";
import type { RunRecord } from "@/lib/types";

/** Deep-link back into the plan form, pre-filled from this run — the HITL refine loop. */
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
  const router = useRouter();
  const { status, nodes, record, error } = useRunStream(runId);
  const terminal = status === "succeeded" || status === "failed";

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex items-center justify-between">
        <Button asChild variant="ghost" size="sm">
          <Link href="/app/trips">
            <ArrowLeft className="size-4" /> Trips
          </Link>
        </Button>
        <div className="flex items-center gap-2">
          {/* HITL: refresh while running; refine-and-regenerate once complete. */}
          <Button variant="outline" size="sm" onClick={() => router.refresh()} disabled={terminal}>
            <RefreshCw className="size-4" /> Refresh
          </Button>
          {terminal && record ? (
            <Button asChild variant="gradient" size="sm">
              <Link href={refineHref(record)}>
                <Sparkles className="size-4" /> Refine this trip
              </Link>
            </Button>
          ) : (
            <Button asChild variant="outline" size="sm">
              <Link href="/app/plan">New trip</Link>
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[20rem_1fr]">
        <div className="lg:sticky lg:top-6 lg:self-start">
          <TraceTimeline nodes={nodes} status={status} />
          {error && (
            <p className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
              {error}
            </p>
          )}
        </div>

        <div>
          {terminal && record ? (
            <div className="space-y-6">
              <MapView record={record} />
              <ItineraryView record={record} />
            </div>
          ) : (
            <div className="space-y-4">
              <div className="h-32 animate-pulse rounded-2xl border border-border bg-muted/40" />
              <div className="h-48 animate-pulse rounded-2xl border border-border bg-muted/40" />
              <p className="text-center text-sm text-muted-foreground">
                Agents are planning your trip — this updates live.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
