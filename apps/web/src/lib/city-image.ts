/**
 * A cover photo for any city. Exact matches use the curated catalogue; unknown
 * cities get a deterministic (stable per name) scenic fallback so every itinerary
 * still has a beautiful, consistent header image.
 */
import { destImage, destinations } from "@/lib/destinations";

// Scenic, landscape-friendly fallbacks (verified Unsplash IDs from the catalogue).
const FALLBACKS = [
  "photo-1493976040374-85c8e12f0c0e", // Kyoto
  "photo-1537996194471-e657df975ab4", // Bali
  "photo-1558642452-9d2a7deb7f62", // Reykjavik
  "photo-1605130284535-11dd9eedc58a", // Cape Town
  "photo-1506973035872-a4ec16b8e8d9", // Sydney
  "photo-1555992336-fb0d29498b13", // Lisbon
];

export function cityImage(city: string, w = 1200): string {
  const key = city.trim().toLowerCase();
  const match = destinations.find((d) => d.name.toLowerCase() === key);
  if (match) return destImage(match.photoId, w);

  let hash = 0;
  for (let i = 0; i < key.length; i++) hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
  return destImage(FALLBACKS[hash % FALLBACKS.length], w);
}
