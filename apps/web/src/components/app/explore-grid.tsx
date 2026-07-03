"use client";

import { Search } from "lucide-react";
import * as React from "react";

import { DestinationCard } from "@/components/app/destination-card";
import { Input } from "@/components/ui/input";
import { type Destination, destinations } from "@/lib/destinations";
import { cn } from "@/lib/utils";

const REGIONS = ["All", "Asia", "Europe", "Americas", "Africa", "Oceania", "Middle East"] as const;

export function ExploreGrid({ initialQuery = "" }: { initialQuery?: string }) {
  const [query, setQuery] = React.useState(initialQuery);
  const [region, setRegion] = React.useState<(typeof REGIONS)[number]>("All");

  const results = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    return destinations.filter((d: Destination) => {
      const matchesRegion = region === "All" || d.region === region;
      const matchesQuery =
        !q ||
        d.name.toLowerCase().includes(q) ||
        d.country.toLowerCase().includes(q) ||
        d.tags.some((t) => t.toLowerCase().includes(q)) ||
        d.interests.some((t) => t.toLowerCase().includes(q));
      return matchesRegion && matchesQuery;
    });
  }, [query, region]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search destinations or interests…"
            className="pl-9"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {REGIONS.map((r) => (
            <button
              key={r}
              onClick={() => setRegion(r)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-sm transition-colors",
                region === r
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border text-muted-foreground hover:border-primary/40",
              )}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {results.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
          No destinations match “{query}”. Try a different search.
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
          {results.map((dest, i) => (
            <DestinationCard key={dest.slug} dest={dest} priority={i < 4} />
          ))}
        </div>
      )}
    </div>
  );
}
