import { afterEach, describe, expect, it } from "vitest";

import { addRecentTrip, loadRecentTrips, removeRecentTrip, toggleFavorite } from "@/lib/recent";

afterEach(() => window.localStorage.clear());

function trip(runId: string, createdAt: number) {
  return { runId, kind: "plan" as const, title: runId, createdAt };
}

describe("recent trips", () => {
  it("returns newest first", () => {
    addRecentTrip(trip("a", 1));
    addRecentTrip(trip("b", 2));
    expect(loadRecentTrips().map((t) => t.runId)).toEqual(["b", "a"]);
  });

  it("sorts favorites ahead of newer non-favorites", () => {
    addRecentTrip(trip("old", 1));
    addRecentTrip(trip("new", 2));
    toggleFavorite("old");
    expect(loadRecentTrips().map((t) => t.runId)).toEqual(["old", "new"]);
  });

  it("removes a trip", () => {
    addRecentTrip(trip("a", 1));
    removeRecentTrip("a");
    expect(loadRecentTrips()).toHaveLength(0);
  });
});
