import { MapPlus } from "lucide-react";
import Link from "next/link";

import { RecentTrips } from "@/components/app/recent-trips";
import { Button } from "@/components/ui/button";

export default function TripsPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Your trips</h1>
          <p className="mt-2 text-muted-foreground">Every itinerary you&apos;ve planned, in one place.</p>
        </div>
        <Button asChild variant="gradient">
          <Link href="/app/plan">
            <MapPlus className="size-4" /> New trip
          </Link>
        </Button>
      </div>
      <RecentTrips />
    </div>
  );
}
