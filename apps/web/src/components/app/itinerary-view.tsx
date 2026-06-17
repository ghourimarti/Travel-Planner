"use client";

import { AlertTriangle, CloudSun, MapPin, ShieldCheck, Wallet } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Itinerary, RunRecord, TripItinerary } from "@/lib/types";
import { formatUsd } from "@/lib/utils";

export function ItineraryView({ record }: { record: RunRecord }) {
  if (record.status === "failed") {
    return (
      <div className="rounded-2xl border border-red-500/30 bg-red-500/5 p-6">
        <div className="flex items-center gap-2 font-semibold text-red-600 dark:text-red-400">
          <AlertTriangle className="size-5" /> Planning failed
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          {record.error ?? "The run did not complete. Please try again."}
        </p>
      </div>
    );
  }

  if (!record.result) {
    return (
      <div className="rounded-2xl border border-border bg-card p-6 text-sm text-muted-foreground">
        Itinerary is being finalized…
      </div>
    );
  }

  if (record.kind === "trip") {
    const trip = record.result as unknown as TripItinerary;
    return (
      <div className="space-y-6">
        <SummaryCard
          title="Your multi-city trip"
          summary={trip.summary_markdown}
          cost={trip.cost_usd}
          warnings={trip.warnings}
        />
        {trip.failed_cities?.length > 0 && (
          <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-amber-700 dark:text-amber-300">
            Some cities couldn&apos;t be planned: {trip.failed_cities.join(", ")}
          </p>
        )}
        {trip.cities?.map((city) => <CityCard key={city.city} itinerary={city} />)}
        {trip.inter_city_legs?.length > 0 && (
          <div className="rounded-2xl border border-border bg-card p-6">
            <h3 className="font-semibold">Inter-city travel</h3>
            <ul className="mt-3 space-y-2 text-sm">
              {trip.inter_city_legs.map((leg, i) => (
                <li key={i} className="flex items-center justify-between border-b border-border pb-2 last:border-0">
                  <span>
                    {leg.from_name} → {leg.to_name}
                  </span>
                  <span className="text-muted-foreground">
                    {Math.round(leg.distance_m / 1000)} km · {Math.round(leg.duration_s / 60)} min
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  }

  const itinerary = record.result as unknown as Itinerary;
  return (
    <div className="space-y-6">
      <SummaryCard
        title={itinerary.city}
        summary={itinerary.summary_markdown}
        cost={itinerary.cost_usd}
        warnings={itinerary.warnings}
        grounded={itinerary.grounded}
      />
      <CityCard itinerary={itinerary} hideSummary />
    </div>
  );
}

function SummaryCard({
  title,
  summary,
  cost,
  warnings,
  grounded,
}: {
  title: string;
  summary: string;
  cost: number;
  warnings?: string[];
  grounded?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold tracking-tight">{title}</h2>
        <div className="flex items-center gap-2">
          {grounded && (
            <Badge variant="success">
              <ShieldCheck className="size-3.5" /> Grounded
            </Badge>
          )}
          <Badge variant="outline">
            <Wallet className="size-3.5" /> {formatUsd(cost)}
          </Badge>
        </div>
      </div>
      {summary && (
        <div className="mt-4 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
          {summary}
        </div>
      )}
      {warnings && warnings.length > 0 && (
        <ul className="mt-4 space-y-1">
          {warnings.map((w, i) => (
            <li key={i} className="flex items-start gap-2 text-xs text-amber-600 dark:text-amber-400">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" /> {w}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CityCard({ itinerary, hideSummary }: { itinerary: Itinerary; hideSummary?: boolean }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-6">
      {!hideSummary && <h3 className="text-lg font-semibold">{itinerary.city}</h3>}

      {itinerary.days?.length > 0 ? (
        <div className="space-y-5">
          {itinerary.days.map((day) => (
            <div key={day.day}>
              <h4 className="text-sm font-semibold text-primary">Day {day.day}</h4>
              <ul className="mt-2 space-y-2">
                {day.items.map((item, i) => (
                  <li key={i} className="flex items-start gap-3 rounded-lg border border-border p-3">
                    <MapPin className="mt-0.5 size-4 shrink-0 text-primary" />
                    <div>
                      <p className="text-sm font-medium">{item.name}</p>
                      <p className="text-xs capitalize text-muted-foreground">{item.category}</p>
                      {item.note && <p className="mt-1 text-xs text-muted-foreground">{item.note}</p>}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      ) : (
        itinerary.pois_used?.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {itinerary.pois_used.slice(0, 24).map((poi, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1 text-xs"
              >
                <MapPin className="size-3 text-primary" /> {poi.name}
              </span>
            ))}
          </div>
        )
      )}

      {itinerary.weather?.length > 0 && (
        <div className="mt-5 border-t border-border pt-4">
          <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <CloudSun className="size-4" /> Forecast
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {itinerary.weather.slice(0, 10).map((w) => (
              <span key={w.date} className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                {w.date}: {w.temp_min_c ?? "—"}–{w.temp_max_c ?? "—"}°C
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
