import { PlanForm, type PlanFormInitial } from "@/components/app/plan-form";

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

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">
          {initial ? "Refine your trip" : "Plan a trip"}
        </h1>
        <p className="mt-2 text-muted-foreground">
          {initial
            ? "Tweak the cities, interests or length and regenerate a fresh itinerary."
            : "Tell Voyantra where you're going and what you love. A team of agents will build a grounded itinerary you can watch come together live."}
        </p>
      </div>
      <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
        <PlanForm initial={initial} />
      </div>
    </div>
  );
}
