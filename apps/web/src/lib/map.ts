/**
 * Pure RunRecord -> map geometry. No DOM, so it's unit-tested directly;
 * MapView is then a thin renderer over this. Inter-city lines connect city
 * centers in order (RouteLeg has no coordinates), so cityCenters preserves order.
 */
import type { Itinerary, RunRecord, TripItinerary } from "@/lib/types";

export interface MapPoint {
  lng: number;
  lat: number;
  name: string;
  category?: string;
  kind: "city" | "poi";
}

export interface MapGeometry {
  points: MapPoint[];
  cityCenters: MapPoint[];
}

function isValid(lng: number, lat: number): boolean {
  return (
    Number.isFinite(lng) &&
    Number.isFinite(lat) &&
    Math.abs(lat) <= 90 &&
    Math.abs(lng) <= 180 &&
    !(lng === 0 && lat === 0)
  );
}

function itineraryPoints(it: Itinerary): { pois: MapPoint[]; center: MapPoint | null } {
  const pois: MapPoint[] = [];
  for (const day of it.days ?? []) {
    for (const item of day.items ?? []) {
      if (isValid(item.longitude, item.latitude)) {
        pois.push({
          lng: item.longitude,
          lat: item.latitude,
          name: item.name,
          category: item.category,
          kind: "poi",
        });
      }
    }
  }
  if (pois.length === 0) {
    for (const p of it.pois_used ?? []) {
      if (isValid(p.longitude, p.latitude)) {
        pois.push({ lng: p.longitude, lat: p.latitude, name: p.name, category: p.category, kind: "poi" });
      }
    }
  }
  const c = it.center;
  const center =
    c && isValid(c.longitude, c.latitude)
      ? { lng: c.longitude, lat: c.latitude, name: c.name, kind: "city" as const }
      : null;
  return { pois, center };
}

export function collectMapPoints(record: RunRecord): MapGeometry {
  if (!record.result) return { points: [], cityCenters: [] };

  const itineraries: Itinerary[] =
    record.kind === "trip"
      ? ((record.result as unknown as TripItinerary).cities ?? [])
      : [record.result as unknown as Itinerary];

  const points: MapPoint[] = [];
  const cityCenters: MapPoint[] = [];
  for (const it of itineraries) {
    const { pois, center } = itineraryPoints(it);
    if (center) {
      cityCenters.push(center);
      points.push(center);
    }
    points.push(...pois);
  }
  return { points, cityCenters };
}
