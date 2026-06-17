import { describe, expect, it } from "vitest";

import { collectMapPoints } from "@/lib/map";
import type { RunRecord } from "@/lib/types";

function planRecord(result: unknown): RunRecord {
  return {
    id: "r1",
    kind: "plan",
    status: "succeeded",
    request: {},
    result: result as Record<string, unknown>,
    error: null,
    warnings: [],
    cost_usd: 0,
  };
}

describe("collectMapPoints", () => {
  it("returns nothing when there's no result", () => {
    expect(collectMapPoints({ ...planRecord(null), result: null }).points).toEqual([]);
  });

  it("collects day-item POIs and the city center, dropping invalid coords", () => {
    const geo = collectMapPoints(
      planRecord({
        city: "Tokyo",
        center: { name: "Tokyo", latitude: 35.68, longitude: 139.69 },
        days: [
          { day: 1, items: [{ name: "Senso-ji", category: "temple", latitude: 35.71, longitude: 139.79 }] },
        ],
        pois_used: [],
      }),
    );
    expect(geo.cityCenters).toHaveLength(1);
    expect(geo.points.map((p) => p.name)).toContain("Senso-ji");
    expect(geo.points.map((p) => p.name)).toContain("Tokyo");
  });

  it("falls back to pois_used when days are empty and skips (0,0)", () => {
    const geo = collectMapPoints(
      planRecord({
        city: "X",
        center: null,
        days: [],
        pois_used: [
          { name: "Good", category: "park", latitude: 10, longitude: 10 },
          { name: "Null Island", category: "x", latitude: 0, longitude: 0 },
        ],
      }),
    );
    expect(geo.points.map((p) => p.name)).toEqual(["Good"]);
  });

  it("orders city centers across a multi-city trip", () => {
    const trip: RunRecord = {
      ...planRecord(null),
      kind: "trip",
      result: {
        cities: [
          { city: "A", center: { name: "A", latitude: 1, longitude: 1 }, days: [], pois_used: [] },
          { city: "B", center: { name: "B", latitude: 2, longitude: 2 }, days: [], pois_used: [] },
        ],
      } as unknown as Record<string, unknown>,
    };
    const geo = collectMapPoints(trip);
    expect(geo.cityCenters.map((c) => c.name)).toEqual(["A", "B"]);
  });
});
