import { Sparkles, Star } from "lucide-react";
import Link from "next/link";

import { HeroSearch } from "@/components/marketing/hero-search";
import { destImage } from "@/lib/destinations";

const POPULAR = ["Tokyo", "Paris", "Bali", "Rome", "Kyoto"];

export function Hero() {
  return (
    <section className="relative isolate overflow-hidden">
      <img
        src={destImage("photo-1537996194471-e657df975ab4", 1920)}
        alt="Travel the world with Voyantra"
        className="absolute inset-0 -z-10 size-full object-cover"
      />
      <div className="absolute inset-0 -z-10 bg-gradient-to-br from-black/80 via-black/55 to-black/45" />

      <div className="mx-auto max-w-5xl px-4 py-28 text-center sm:px-6 lg:px-8 lg:py-36">
        <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/10 px-3 py-1 text-xs font-medium text-white backdrop-blur-sm">
          <Sparkles className="size-3.5" /> AI trip planning · real places only
        </div>

        <h1 className="mt-6 text-4xl font-bold tracking-tight text-white sm:text-5xl lg:text-6xl">
          Your next <span className="text-gradient">adventure</span>, planned in seconds.
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-white/85">
          Tell Voyantra where you dream of going and get a complete, day-by-day itinerary in
          seconds — real places, pinned on the map and planned around the weather, with nothing
          made up.
        </p>

        <HeroSearch />

        <div className="mt-5 flex flex-wrap items-center justify-center gap-2 text-sm text-white/80">
          <span>Popular:</span>
          {POPULAR.map((city) => (
            <Link
              key={city}
              href="/signup"
              className="rounded-full border border-white/25 bg-white/5 px-3 py-1 text-xs text-white/90 backdrop-blur-sm transition-colors hover:bg-white/15"
            >
              {city}
            </Link>
          ))}
        </div>

        <div className="mt-8 flex items-center justify-center gap-2 text-sm text-white/85">
          <span className="flex">
            {Array.from({ length: 5 }).map((_, i) => (
              <Star key={i} className="size-4 fill-amber-400 text-amber-400" />
            ))}
          </span>
          <span className="font-semibold">4.9</span>
          <span className="text-white/70">· loved by modern travelers worldwide</span>
        </div>
      </div>
    </section>
  );
}
