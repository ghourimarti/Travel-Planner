import { PlanForm, type PlanFormInitial } from "@/components/app/plan-form";
import { cityImage } from "@/lib/city-image";

export const dynamic = "force-dynamic";

function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

function parseInitial(sp: Record<string, string | string[] | undefined>): PlanFormInitial | undefined {
  const mode = first(sp.mode);
  const city = first(sp.city);
  const cities = first(sp.cities);
  const interests = first(sp.interests);
  const days = first(sp.days);
  if (!mode && !city && !cities && !interests && !days) return undefined;

  return {
    mode: mode === "multi" ? "multi" : mode === "single" ? "single" : undefined,
    city,
    cities: cities ? cities.split(",").map((c) => c.trim()).filter(Boolean) : undefined,
    interests: interests
      ? interests.split(",").map((i) => i.trim()).filter(Boolean)
      : undefined,
    days: days ? Math.max(1, Math.min(10, Number(days) || 3)) : undefined,
  };
}

export default async function PlanPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const initial = parseInitial(await searchParams);
  const coverCity = initial?.city ?? initial?.cities?.[0] ?? "";

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <div className="relative overflow-hidden rounded-2xl border border-border">
        <img src={cityImage(coverCity, 1200)} alt="" className="h-40 w-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/45 to-black/20" />
        <div className="absolute inset-x-0 bottom-0 p-6">
          <h1 className="text-2xl font-bold tracking-tight text-white">
            {initial ? "Refine your trip" : "Plan a trip"}
          </h1>
          <p className="mt-1 max-w-lg text-sm text-white/85">
            {initial
              ? "Tweak the cities, interests or length and regenerate a fresh itinerary."
              : "Tell Voyantra where you're going and what you love — and we'll build your day-by-day itinerary live, in seconds."}
          </p>
        </div>
      </div>
      <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
        <PlanForm initial={initial} />
      </div>
    </div>
  );
}
