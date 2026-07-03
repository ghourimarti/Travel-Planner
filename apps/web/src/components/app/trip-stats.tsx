"use client";

import { Globe2, MapPin, Plane, Star } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import * as React from "react";

import { loadRecentTrips } from "@/lib/recent";

export function TripStats() {
  const [stats, setStats] = React.useState<{
    trips: number;
    cities: number;
    favorites: number;
  } | null>(null);

  React.useEffect(() => {
    const trips = loadRecentTrips();
    const cities = trips.reduce(
      (n, t) => n + t.title.split(/[,&]/).filter((s) => s.trim()).length,
      0,
    );
    setStats({
      trips: trips.length,
      cities,
      favorites: trips.filter((t) => t.favorite).length,
    });
  }, []);

  const items: { label: string; value: number; icon: LucideIcon }[] = [
    { label: "Trips planned", value: stats?.trips ?? 0, icon: Plane },
    { label: "Cities explored", value: stats?.cities ?? 0, icon: MapPin },
    { label: "Saved trips", value: stats?.favorites ?? 0, icon: Star },
    { label: "Destinations to discover", value: 22, icon: Globe2 },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {items.map((s) => (
        <div key={s.label} className="flex items-center gap-3 rounded-xl border border-border bg-card p-4">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <s.icon className="size-5" />
          </span>
          <div>
            <p className="text-xl font-bold leading-none">{s.value}</p>
            <p className="mt-1 text-xs text-muted-foreground">{s.label}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
