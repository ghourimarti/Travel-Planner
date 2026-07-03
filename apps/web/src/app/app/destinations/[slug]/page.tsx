import { ArrowLeft, CalendarDays, Check, MapPin, Sparkles } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { DestinationCard } from "@/components/app/destination-card";
import { Button } from "@/components/ui/button";
import {
  destImage,
  destinations,
  getDestination,
  relatedDestinations,
} from "@/lib/destinations";

export function generateStaticParams() {
  return destinations.map((d) => ({ slug: d.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const dest = getDestination(slug);
  return dest
    ? { title: `${dest.name}, ${dest.country}`, description: dest.blurb }
    : { title: "Destination" };
}

export default async function DestinationPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const dest = getDestination(slug);
  if (!dest) notFound();

  const planHref = `/app/plan?mode=single&city=${encodeURIComponent(
    dest.name,
  )}&interests=${dest.interests.join(",")}&days=3`;
  const related = relatedDestinations(slug);

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <Button asChild variant="ghost" size="sm">
        <Link href="/app/explore">
          <ArrowLeft className="size-4" /> Explore
        </Link>
      </Button>

      {/* Hero */}
      <section className="relative overflow-hidden rounded-3xl border border-border">
        <img
          src={destImage(dest.photoId, 1600)}
          alt={dest.name}
          className="h-72 w-full object-cover sm:h-96"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/35 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 p-6 sm:p-8">
          <p className="flex items-center gap-1.5 text-sm font-medium text-white/90">
            <MapPin className="size-4" /> {dest.country} · {dest.region}
          </p>
          <h1 className="mt-1 text-4xl font-bold tracking-tight text-white sm:text-5xl">
            {dest.name}
          </h1>
          <div className="mt-3 flex flex-wrap gap-2">
            {dest.tags.map((t) => (
              <span
                key={t}
                className="rounded-full bg-white/15 px-3 py-1 text-xs font-medium text-white backdrop-blur-sm"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      </section>

      <div className="grid gap-8 lg:grid-cols-[1fr_18rem]">
        <div className="space-y-8">
          <section>
            <h2 className="text-xl font-bold tracking-tight">About {dest.name}</h2>
            <p className="mt-3 leading-relaxed text-muted-foreground">{dest.blurb}</p>
          </section>

          <section>
            <h2 className="text-xl font-bold tracking-tight">Top highlights</h2>
            <ul className="mt-4 grid gap-3 sm:grid-cols-2">
              {dest.highlights.map((h) => (
                <li
                  key={h}
                  className="flex items-center gap-3 rounded-xl border border-border bg-card p-4"
                >
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Check className="size-4" />
                  </span>
                  <span className="text-sm font-medium">{h}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>

        {/* Plan sidebar */}
        <aside className="lg:sticky lg:top-6 lg:self-start">
          <div className="rounded-2xl border border-border bg-card p-6">
            <h3 className="font-semibold">Plan your trip</h3>
            <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
              <CalendarDays className="size-4 text-primary" />
              <span>Best time: {dest.bestSeason}</span>
            </div>
            <p className="mt-4 text-sm text-muted-foreground">
              We&apos;ll build a complete, day-by-day itinerary for {dest.name} around{" "}
              {dest.interests.join(", ")}.
            </p>
            <Button asChild variant="gradient" size="lg" className="mt-5 w-full">
              <Link href={planHref}>
                <Sparkles className="size-4" /> Plan a trip to {dest.name}
              </Link>
            </Button>
          </div>
        </aside>
      </div>

      {/* Related */}
      <section>
        <h2 className="mb-5 text-xl font-bold tracking-tight">You might also like</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {related.map((d) => (
            <DestinationCard key={d.slug} dest={d} />
          ))}
        </div>
      </section>
    </div>
  );
}
