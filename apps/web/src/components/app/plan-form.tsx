"use client";

import { Loader2, MapPin, Plus, Sparkles, X } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { addRecentTrip } from "@/lib/recent";
import type { RunAccepted } from "@/lib/types";
import { cn, joinCities } from "@/lib/utils";

const SUGGESTED_INTERESTS = [
  "temples",
  "museums",
  "food",
  "nightlife",
  "nature",
  "history",
  "shopping",
  "art",
  "architecture",
  "beaches",
];

type Mode = "single" | "multi";

export interface PlanFormInitial {
  mode?: Mode;
  city?: string;
  cities?: string[];
  interests?: string[];
  days?: number;
}

export function PlanForm({ initial }: { initial?: PlanFormInitial }) {
  const router = useRouter();
  const [mode, setMode] = React.useState<Mode>(
    initial?.mode ?? ((initial?.cities?.length ?? 0) > 1 ? "multi" : "single"),
  );
  const [city, setCity] = React.useState(initial?.city ?? "");
  const [cities, setCities] = React.useState<string[]>(
    initial?.cities && initial.cities.length >= 2 ? initial.cities : (initial?.cities ?? ["", ""]),
  );
  const [interests, setInterests] = React.useState<string[]>(
    initial?.interests && initial.interests.length > 0 ? initial.interests : ["food", "history"],
  );
  const [customInterest, setCustomInterest] = React.useState("");
  const [days, setDays] = React.useState(initial?.days ?? 3);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const maxDays = mode === "single" ? 3 : 10;
  React.useEffect(() => {
    setDays((d) => Math.min(d, maxDays));
  }, [maxDays]);

  function toggleInterest(value: string) {
    setInterests((prev) =>
      prev.includes(value) ? prev.filter((i) => i !== value) : [...prev, value],
    );
  }

  function addCustomInterest() {
    const v = customInterest.trim().toLowerCase();
    if (v && !interests.includes(v)) setInterests((prev) => [...prev, v]);
    setCustomInterest("");
  }

  function updateCity(idx: number, value: string) {
    setCities((prev) => prev.map((c, i) => (i === idx ? value : c)));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const cleanCities =
      mode === "single" ? [city.trim()] : cities.map((c) => c.trim()).filter(Boolean);

    if (cleanCities.length === 0 || cleanCities.some((c) => !c)) {
      setError("Please enter at least one city.");
      return;
    }
    if (interests.length === 0) {
      setError("Pick at least one interest.");
      return;
    }

    setSubmitting(true);
    try {
      const isTrip = mode === "multi";
      const endpoint = isTrip ? "/api/trip" : "/api/plan";
      const body = isTrip
        ? { cities: cleanCities, interests, days }
        : { city: cleanCities[0], interests, days };

      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(
          res.status === 503
            ? "Planning is temporarily disabled. Please try again shortly."
            : res.status === 429
              ? "You've hit the rate limit. Please wait a moment."
              : (detail.error ?? `Request failed (${res.status}).`),
        );
      }

      const accepted = (await res.json()) as RunAccepted;
      addRecentTrip({
        runId: accepted.run_id,
        kind: isTrip ? "trip" : "plan",
        title: joinCities(cleanCities),
        createdAt: Date.now(),
      });
      router.push(`/app/runs/${accepted.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-8">
      <Tabs value={mode} onValueChange={(v) => setMode(v as Mode)}>
        <TabsList className="grid w-full max-w-sm grid-cols-2">
          <TabsTrigger value="single">Single city</TabsTrigger>
          <TabsTrigger value="multi">Multi-city</TabsTrigger>
        </TabsList>

        <TabsContent value="single">
          <div className="space-y-2">
            <Label htmlFor="city">Destination</Label>
            <div className="relative">
              <MapPin className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="city"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="e.g. Tokyo"
                className="pl-9"
              />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="multi">
          <div className="space-y-3">
            <Label>Destinations (up to 5)</Label>
            {cities.map((c, i) => (
              <div key={i} className="flex gap-2">
                <div className="relative flex-1">
                  <MapPin className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={c}
                    onChange={(e) => updateCity(i, e.target.value)}
                    placeholder={`City ${i + 1}`}
                    className="pl-9"
                  />
                </div>
                {cities.length > 2 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => setCities((prev) => prev.filter((_, idx) => idx !== i))}
                    aria-label="Remove city"
                  >
                    <X className="size-4" />
                  </Button>
                )}
              </div>
            ))}
            {cities.length < 5 && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setCities((prev) => [...prev, ""])}
              >
                <Plus className="size-4" /> Add city
              </Button>
            )}
          </div>
        </TabsContent>
      </Tabs>

      <div className="space-y-3">
        <Label>Interests</Label>
        <div className="flex flex-wrap gap-2">
          {Array.from(new Set([...SUGGESTED_INTERESTS, ...interests])).map((interest) => {
            const selected = interests.includes(interest);
            return (
              <button
                key={interest}
                type="button"
                onClick={() => toggleInterest(interest)}
                className={cn(
                  "rounded-full border px-3 py-1.5 text-sm capitalize transition-colors",
                  selected
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:border-primary/40",
                )}
              >
                {interest}
              </button>
            );
          })}
        </div>
        <div className="flex max-w-sm gap-2">
          <Input
            value={customInterest}
            onChange={(e) => setCustomInterest(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addCustomInterest();
              }
            }}
            placeholder="Add your own…"
          />
          <Button type="button" variant="outline" onClick={addCustomInterest}>
            Add
          </Button>
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label htmlFor="days">Trip length</Label>
          <span className="text-sm font-medium text-primary">
            {days} {days === 1 ? "day" : "days"}
          </span>
        </div>
        <input
          id="days"
          type="range"
          min={1}
          max={maxDays}
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="w-full accent-[var(--color-primary)]"
        />
      </div>

      {error && (
        <p className="rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}

      <Button type="submit" size="lg" variant="gradient" disabled={submitting} className="w-full sm:w-auto">
        {submitting ? (
          <>
            <Loader2 className="size-4 animate-spin" /> Dispatching agents…
          </>
        ) : (
          <>
            <Sparkles className="size-4" /> Generate itinerary
          </>
        )}
      </Button>
    </form>
  );
}
