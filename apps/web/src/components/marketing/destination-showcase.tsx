import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { DestinationCard } from "@/components/app/destination-card";
import { Button } from "@/components/ui/button";
import { destinations } from "@/lib/destinations";

const SHOWCASE = destinations.slice(0, 8);

export function DestinationShowcase() {
  return (
    <section className="border-y border-border bg-muted/20">
      <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Explore the world&apos;s most loved destinations
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            From Tokyo&apos;s neon streets to Bali&apos;s rice terraces — start with a place that
            inspires you and let Voyantra plan the rest.
          </p>
        </div>

        <div className="mt-14 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
          {SHOWCASE.map((dest, i) => (
            <DestinationCard key={dest.slug} dest={dest} href="/signup" priority={i < 4} />
          ))}
        </div>

        <div className="mt-10 text-center">
          <Button asChild size="lg" variant="gradient">
            <Link href="/signup">
              Start exploring free <ArrowRight className="size-4" />
            </Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
