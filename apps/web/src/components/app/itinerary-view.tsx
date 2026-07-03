"use client";

import {
  AlertTriangle,
  Building2,
  CloudSun,
  Landmark,
  Moon,
  MapPin,
  Palette,
  ScrollText,
  ShieldCheck,
  ShoppingBag,
  UtensilsCrossed,
  Waves,
  Trees,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Badge } from "@/components/ui/badge";
import { cityImage } from "@/lib/city-image";
import type { Itinerary, ItineraryItem, RunRecord, TripItinerary } from "@/lib/types";
import { cn } from "@/lib/utils";

const CATEGORY_CONFIG: Record<string, { icon: LucideIcon; color: string; label: string }> = {
  food:         { icon: UtensilsCrossed, color: "text-orange-500 bg-orange-500/10", label: "Food & Dining" },
  museum:       { icon: Landmark,        color: "text-blue-500 bg-blue-500/10",     label: "Museum" },
  museums:      { icon: Landmark,        color: "text-blue-500 bg-blue-500/10",     label: "Museum" },
  temple:       { icon: Building2,       color: "text-purple-500 bg-purple-500/10", label: "Temple" },
  temples:      { icon: Building2,       color: "text-purple-500 bg-purple-500/10", label: "Temple" },
  nightlife:    { icon: Moon,            color: "text-indigo-500 bg-indigo-500/10", label: "Nightlife" },
  nature:       { icon: Trees,           color: "text-green-500 bg-green-500/10",   label: "Nature" },
  history:      { icon: ScrollText,      color: "text-amber-600 bg-amber-500/10",   label: "History" },
  shopping:     { icon: ShoppingBag,     color: "text-pink-500 bg-pink-500/10",     label: "Shopping" },
  art:          { icon: Palette,         color: "text-rose-500 bg-rose-500/10",     label: "Art" },
  architecture: { icon: Building2,       color: "text-slate-500 bg-slate-500/10",   label: "Architecture" },
  beach:        { icon: Waves,           color: "text-cyan-500 bg-cyan-500/10",     label: "Beach" },
  beaches:      { icon: Waves,           color: "text-cyan-500 bg-cyan-500/10",     label: "Beach" },
};

const TIME_SLOTS = ["Morning", "Afternoon", "Evening", "Night"];

function getCategoryConfig(category: string) {
  return (
    CATEGORY_CONFIG[category.toLowerCase()] ?? {
      icon: MapPin,
      color: "text-primary bg-primary/10",
      label: category,
    }
  );
}

function ItineraryItemCard({ item, index }: { item: ItineraryItem; index: number }) {
  const { icon: Icon, color, label } = getCategoryConfig(item.category);
  const timeSlot = TIME_SLOTS[Math.min(index, TIME_SLOTS.length - 1)];
  return (
    <div className="flex items-start gap-3 rounded-xl border border-border bg-background p-4 transition-colors hover:bg-muted/30">
      <div className={cn("flex size-10 shrink-0 items-center justify-center rounded-xl", color)}>
        <Icon className="size-5" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-semibold leading-snug">{item.name}</p>
          <span className="shrink-0 text-xs text-muted-foreground">{timeSlot}</span>
        </div>
        <p className="mt-0.5 text-xs capitalize text-muted-foreground">{label}</p>
        {item.note && (
          <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{item.note}</p>
        )}
      </div>
    </div>
  );
}

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
          warnings={trip.warnings}
          coverCity={trip.cities?.[0]?.city}
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
        warnings={itinerary.warnings}
        grounded={itinerary.grounded}
        coverCity={itinerary.city}
      />
      <CityCard itinerary={itinerary} hideSummary />
    </div>
  );
}

function SummaryCard({
  title,
  summary,
  warnings,
  grounded,
  coverCity,
}: {
  title: string;
  summary: string;
  cost?: number;
  warnings?: string[];
  grounded?: boolean;
  coverCity?: string;
}) {
  const displayTitle = title
    .split(" ")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card">
      {coverCity && (
        <div className="relative h-44 w-full sm:h-52">
          <img src={cityImage(coverCity, 1400)} alt={displayTitle} className="size-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/30 to-transparent" />
          <div className="absolute inset-x-0 bottom-0 flex flex-wrap items-end justify-between gap-3 p-5">
            <h2 className="text-3xl font-bold tracking-tight text-white">{displayTitle}</h2>
            {grounded && (
              <Badge variant="success">
                <ShieldCheck className="size-3.5" /> AI-verified itinerary
              </Badge>
            )}
          </div>
        </div>
      )}
      <div className="p-6">
        {!coverCity && (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-2xl font-bold tracking-tight">{displayTitle}</h2>
            {grounded && (
              <Badge variant="success">
                <ShieldCheck className="size-3.5" /> AI-verified itinerary
              </Badge>
            )}
          </div>
        )}
        {summary && (
          <div className="prose prose-sm dark:prose-invert max-w-none text-muted-foreground [&_h3]:text-base [&_h3]:font-semibold [&_h3]:text-foreground [&_strong]:text-foreground [&_ul]:my-1 [&_li]:my-0.5">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{summary}</ReactMarkdown>
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
    </div>
  );
}

function CityCard({ itinerary, hideSummary }: { itinerary: Itinerary; hideSummary?: boolean }) {
  const cityTitle = itinerary.city.charAt(0).toUpperCase() + itinerary.city.slice(1);
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card">
      {!hideSummary && (
        <div className="relative h-40 w-full">
          <img
            src={cityImage(itinerary.city, 1200)}
            alt={cityTitle}
            className="size-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/80 to-transparent" />
          <h3 className="absolute bottom-4 left-5 text-2xl font-bold tracking-tight text-white">
            {cityTitle}
          </h3>
        </div>
      )}

      <div className="p-6">
        {itinerary.days?.length > 0 ? (
        <div className="space-y-6">
          {itinerary.days.map((day) => (
            <div key={day.day}>
              <div className="mb-3 flex items-center gap-3">
                <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                  {day.day}
                </div>
                <h4 className="text-sm font-semibold">Day {day.day}</h4>
                <div className="h-px flex-1 bg-border" />
              </div>
              <div className="space-y-2 pl-10">
                {day.items.map((item, i) => (
                  <ItineraryItemCard key={i} item={item} index={i} />
                ))}
              </div>
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
        <div className="mt-6 rounded-xl border border-border bg-muted/30 p-4">
          <p className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <CloudSun className="size-4" /> Weather forecast
          </p>
          <div className="flex flex-wrap gap-2">
            {itinerary.weather.slice(0, 7).map((w) => (
              <div key={w.date} className="rounded-lg border border-border bg-card px-3 py-2 text-center">
                <p className="text-xs text-muted-foreground">
                  {new Date(w.date).toLocaleDateString("en", { weekday: "short", month: "short", day: "numeric" })}
                </p>
                <p className="mt-1 text-sm font-semibold">
                  {w.temp_min_c ?? "—"}–{w.temp_max_c ?? "—"}°C
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
