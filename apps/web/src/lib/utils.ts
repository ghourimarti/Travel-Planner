import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge conditional + conflicting Tailwind classes (the shadcn `cn` helper). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** "Tokyo", "Kyoto" -> "Tokyo & Kyoto"; ["a","b","c"] -> "a, b & c". */
export function joinCities(cities: string[]): string {
  if (cities.length <= 1) return cities[0] ?? "";
  return `${cities.slice(0, -1).join(", ")} & ${cities[cities.length - 1]}`;
}

export function formatUsd(value: number | null | undefined): string {
  if (value == null) return "—";
  return value < 0.01 ? `$${value.toFixed(4)}` : `$${value.toFixed(2)}`;
}
