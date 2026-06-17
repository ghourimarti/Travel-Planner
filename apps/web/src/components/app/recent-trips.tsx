"use client";

import { ArrowRight, MapPin, Plane, Star, Trash2 } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import {
  type RecentTrip,
  loadRecentTrips,
  removeRecentTrip,
  toggleFavorite,
} from "@/lib/recent";
import { cn } from "@/lib/utils";

export function RecentTrips({ limit }: { limit?: number }) {
  const [trips, setTrips] = React.useState<RecentTrip[] | null>(null);

  const refresh = React.useCallback(() => {
    const all = loadRecentTrips();
    setTrips(limit ? all.slice(0, limit) : all);
  }, [limit]);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  if (trips === null) {
    return <div className="h-24 animate-pulse rounded-xl border border-border bg-muted/40" />;
  }

  if (trips.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border p-8 text-center">
        <Plane className="mx-auto size-8 text-muted-foreground/50" />
        <p className="mt-3 text-sm text-muted-foreground">
          No trips yet. Plan your first one to see it here.
        </p>
        <Link
          href="/app/plan"
          className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          Plan a trip <ArrowRight className="size-4" />
        </Link>
      </div>
    );
  }

  return (
    <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border">
      {trips.map((t) => (
        <li key={t.runId} className="group flex items-center gap-1 pr-2 transition-colors hover:bg-muted/50">
          <Link href={`/app/runs/${t.runId}`} className="flex min-w-0 flex-1 items-center gap-3 py-3 pl-4">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <MapPin className="size-4" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{t.title}</p>
              <p className="text-xs text-muted-foreground">
                {t.kind === "trip" ? "Multi-city" : "Single city"} ·{" "}
                {new Date(t.createdAt).toLocaleDateString()}
              </p>
            </div>
          </Link>

          <button
            aria-label={t.favorite ? "Unfavorite" : "Favorite"}
            onClick={() => {
              toggleFavorite(t.runId);
              refresh();
            }}
            className={cn(
              "rounded-md p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-amber-500",
              t.favorite && "text-amber-500",
            )}
          >
            <Star className={cn("size-4", t.favorite && "fill-current")} />
          </button>
          <button
            aria-label="Delete trip"
            onClick={() => {
              removeRecentTrip(t.runId);
              refresh();
            }}
            className="rounded-md p-2 text-muted-foreground opacity-0 transition-colors hover:bg-muted hover:text-red-500 focus:opacity-100 group-hover:opacity-100"
          >
            <Trash2 className="size-4" />
          </button>
        </li>
      ))}
    </ul>
  );
}
