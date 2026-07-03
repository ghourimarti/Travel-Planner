import { ExploreGrid } from "@/components/app/explore-grid";

export const dynamic = "force-dynamic";

function first(v: string | string[] | undefined): string {
  return (Array.isArray(v) ? v[0] : v) ?? "";
}

export default async function ExplorePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const initialQuery = first(sp.interest) || first(sp.q);

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Explore destinations</h1>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          Browse hand-picked destinations from around the world, then plan a complete itinerary in
          a single click.
        </p>
      </header>
      <ExploreGrid initialQuery={initialQuery} />
    </div>
  );
}
