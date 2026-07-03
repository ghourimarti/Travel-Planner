import { ArrowRight, Compass, MapPlus, Plane, Sparkles } from "lucide-react";
import Link from "next/link";

import { DestinationCard } from "@/components/app/destination-card";
import { QuickPlan } from "@/components/app/quick-plan";
import { RecentTrips } from "@/components/app/recent-trips";
import { TripStats } from "@/components/app/trip-stats";
import { Button } from "@/components/ui/button";
import { destImage, destinations } from "@/lib/destinations";

const POPULAR = destinations.slice(0, 8);
const INTEREST_CHIPS = [
  "food",
  "history",
  "temples",
  "nature",
  "nightlife",
  "art",
  "beaches",
  "shopping",
];

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-12">
      {/* Photo hero */}
      <section className="relative overflow-hidden rounded-3xl border border-border">
        <img
          src={destImage("photo-1493976040374-85c8e12f0c0e", 1600)}
          alt="Travel inspiration"
          className="absolute inset-0 size-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-br from-black/85 via-black/55 to-black/30" />
        <div className="relative px-6 py-12 sm:px-10 sm:py-16">
          <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-medium text-white backdrop-blur-sm">
            <Sparkles className="size-3.5" /> AI trip planning · real places only
          </div>
          <h1 className="mt-5 max-w-2xl text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Where to next?
          </h1>
          <p className="mt-3 max-w-xl text-white/80">
            Get a complete, day-by-day itinerary for any destination in under a minute — real
            places, pinned on the map and planned around the weather.
          </p>
          <QuickPlan className="mt-6 max-w-xl" />
          <div className="mt-4 flex flex-wrap gap-2">
            {INTEREST_CHIPS.map((interest) => (
              <Link
                key={interest}
                href={`/app/explore?interest=${interest}`}
                className="rounded-full border border-white/20 bg-white/5 px-3 py-1 text-xs capitalize text-white/90 backdrop-blur-sm transition-colors hover:bg-white/15"
              >
                {interest}
              </Link>
            ))}
          </div>
        </div>
      </section>

      <TripStats />

      {/* Popular destinations */}
      <section>
        <div className="mb-5 flex items-end justify-between">
          <div>
            <h2 className="text-xl font-bold tracking-tight">Popular destinations</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Hand-picked places travelers love right now.
            </p>
          </div>
          <Button asChild variant="ghost" size="sm">
            <Link href="/app/explore">
              <Compass className="size-4" /> Explore all
            </Link>
          </Button>
        </div>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
          {POPULAR.map((dest, i) => (
            <DestinationCard key={dest.slug} dest={dest} priority={i < 4} />
          ))}
        </div>
      </section>

      {/* CTA band */}
      <section className="flex flex-col items-start justify-between gap-4 rounded-2xl border border-border bg-gradient-to-br from-primary/10 to-secondary/10 p-6 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-lg font-bold tracking-tight">Have somewhere specific in mind?</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Plan a single city or a multi-city trip across up to five destinations.
          </p>
        </div>
        <div className="flex gap-3">
          <Button asChild variant="gradient">
            <Link href="/app/plan">
              <MapPlus className="size-4" /> Plan a trip
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/app/trips">
              <Plane className="size-4" /> My trips
            </Link>
          </Button>
        </div>
      </section>

      {/* Recent trips */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xl font-bold tracking-tight">Recent trips</h2>
          <Link
            href="/app/trips"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            View all <ArrowRight className="size-4" />
          </Link>
        </div>
        <RecentTrips limit={5} />
      </section>
    </div>
  );
}
