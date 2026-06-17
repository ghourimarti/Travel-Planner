/** Client-side recent-trip history (localStorage) — there's no list endpoint yet. */

export interface RecentTrip {
  runId: string;
  kind: "plan" | "trip";
  title: string;
  createdAt: number;
  favorite?: boolean;
}

const KEY = "voyantra:recent-trips";
const MAX = 50;

function sortTrips(trips: RecentTrip[]): RecentTrip[] {
  return [...trips].sort((a, b) => {
    if (Boolean(b.favorite) !== Boolean(a.favorite)) return a.favorite ? -1 : 1;
    return b.createdAt - a.createdAt;
  });
}

function readRaw(): RecentTrip[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as RecentTrip[]) : [];
  } catch {
    return [];
  }
}

function writeRaw(trips: RecentTrip[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(trips.slice(0, MAX)));
  } catch {
    // history is a nicety, not critical — ignore quota/serialization errors
  }
}

export function loadRecentTrips(): RecentTrip[] {
  return sortTrips(readRaw());
}

export function addRecentTrip(trip: RecentTrip): void {
  const existing = readRaw().filter((t) => t.runId !== trip.runId);
  writeRaw([trip, ...existing]);
}

export function updateRecentTrip(runId: string, patch: Partial<RecentTrip>): void {
  writeRaw(readRaw().map((t) => (t.runId === runId ? { ...t, ...patch } : t)));
}

export function removeRecentTrip(runId: string): void {
  writeRaw(readRaw().filter((t) => t.runId !== runId));
}

export function toggleFavorite(runId: string): void {
  const t = readRaw().find((x) => x.runId === runId);
  if (t) updateRecentTrip(runId, { favorite: !t.favorite });
}
