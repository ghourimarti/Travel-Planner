import { ArrowRight, MapPlus, Plane, Sparkles } from "lucide-react";
import Link from "next/link";

import { RecentTrips } from "@/components/app/recent-trips";
import { Button } from "@/components/ui/button";
import { stats } from "@/lib/content";

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-10">
      <div className="relative overflow-hidden rounded-2xl border border-border bg-card p-8">
        <div className="pointer-events-none absolute -right-10 -top-10 size-48 rounded-full bg-[radial-gradient(circle,var(--color-brand-1),transparent_60%)] opacity-20 blur-2xl" />
        <div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/40 px-3 py-1 text-xs text-muted-foreground">
          <Sparkles className="size-3.5 text-primary" /> Welcome back
        </div>
        <h1 className="mt-4 text-3xl font-bold tracking-tight">Where to next?</h1>
        <p className="mt-2 max-w-lg text-muted-foreground">
          Spin up a grounded, multi-agent itinerary in seconds. Pick your cities and interests, and
          watch the agents build your plan live.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Button asChild size="lg" variant="gradient">
            <Link href="/app/plan">
              <MapPlus className="size-4" /> Plan a trip
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="/app/trips">
              <Plane className="size-4" /> View trips
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="rounded-xl border border-border bg-card p-5">
            <p className="text-2xl font-bold tracking-tight text-gradient">{s.value}</p>
            <p className="mt-1 text-xs text-muted-foreground">{s.label}</p>
          </div>
        ))}
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Recent trips</h2>
          <Link
            href="/app/trips"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            View all <ArrowRight className="size-4" />
          </Link>
        </div>
        <RecentTrips limit={5} />
      </div>
    </div>
  );
}
