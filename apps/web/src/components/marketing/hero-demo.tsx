"use client";

import { Check, Loader2, MapPin } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

const NODES = [
  { key: "geocode", label: "Finding destinations", detail: "Tokyo · Kyoto · Osaka" },
  { key: "gather", label: "Discovering places", detail: "142 spots · weather · routes" },
  { key: "compose", label: "Building itinerary", detail: "Your 6-day plan" },
  { key: "critic", label: "Double-checking", detail: "Every place verified ✓" },
];

/** Looping decorative preview of the live planning view, to show what the product feels like. */
export function HeroDemo() {
  const [active, setActive] = React.useState(0);

  React.useEffect(() => {
    const t = setInterval(() => setActive((a) => (a + 1) % (NODES.length + 1)), 1100);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="relative animate-float-up rounded-2xl border border-border bg-card/80 p-5 shadow-2xl backdrop-blur">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2 text-sm font-medium">
          <span className="flex size-6 items-center justify-center rounded-md bg-primary/10 text-primary">
            <MapPin className="size-4" />
          </span>
          Planning · Japan trip
        </div>
        <span className="text-xs text-muted-foreground">live</span>
      </div>

      <ol className="mt-4 space-y-2.5">
        {NODES.map((node, i) => {
          const done = i < active;
          const running = i === active;
          return (
            <li
              key={node.key}
              className={cn(
                "flex items-center gap-3 rounded-lg border px-3 py-2.5 transition-all",
                done && "border-emerald-500/30 bg-emerald-500/5",
                running && "border-primary/40 bg-primary/5",
                !done && !running && "border-border opacity-50",
              )}
            >
              <span
                className={cn(
                  "flex size-6 shrink-0 items-center justify-center rounded-full text-xs",
                  done && "bg-emerald-500/15 text-emerald-500",
                  running && "bg-primary/15 text-primary",
                  !done && !running && "bg-muted text-muted-foreground",
                )}
              >
                {done ? (
                  <Check className="size-3.5" />
                ) : running ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  i + 1
                )}
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium">{node.label}</p>
                <p className="truncate text-xs text-muted-foreground">{node.detail}</p>
              </div>
            </li>
          );
        })}
      </ol>

      <div className="mt-4 flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
        <span>6 days · 3 cities</span>
        <span>{active > NODES.length - 1 ? "itinerary ready ✓" : "planning…"}</span>
      </div>
    </div>
  );
}
