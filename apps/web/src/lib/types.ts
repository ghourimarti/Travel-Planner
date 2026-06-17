/**
 * TypeScript mirror of the FastAPI/Pydantic contract (packages/agents/schemas.py,
 * packages/core/runs.py, packages/core/events.py). This is hand-kept in lockstep
 * with the backend so the UI cannot silently drift from the API. If the backend
 * schema changes, this file changes in the same PR.
 */

// ----- auth -----------------------------------------------------------------
/** The authenticated app user, from either Auth0 or the built-in dev session. */
export interface AppUser {
  sub: string;
  name?: string;
  email?: string;
}

// ----- requests -------------------------------------------------------------
export interface PlanRequest {
  city: string;
  interests: string[];
  days: number; // 1..3
}

export interface TripRequest {
  cities: string[]; // 1..5
  interests: string[];
  days: number; // 1..10
}

// ----- tool models ----------------------------------------------------------
export interface GeoLocation {
  name: string;
  latitude: number;
  longitude: number;
  country?: string | null;
  display_name?: string | null;
}

export interface POI {
  name: string;
  category: string;
  latitude: number;
  longitude: number;
  address?: string | null;
}

export interface WeatherDaily {
  date: string;
  temp_max_c?: number | null;
  temp_min_c?: number | null;
  precipitation_mm?: number | null;
  weather_code?: number | null;
}

export interface RouteLeg {
  from_name: string;
  to_name: string;
  distance_m: number;
  duration_s: number;
}

// ----- itinerary ------------------------------------------------------------
export interface ItineraryItem {
  name: string;
  category: string;
  latitude: number;
  longitude: number;
  note?: string | null;
}

export interface DayPlan {
  day: number;
  items: ItineraryItem[];
}

export interface Itinerary {
  city: string;
  summary_markdown: string;
  days: DayPlan[];
  pois_used: POI[];
  weather: WeatherDaily[];
  warnings: string[];
  grounded: boolean;
  cost_usd: number;
  corrections: number;
  center?: GeoLocation | null;
}

export interface TripItinerary {
  summary_markdown: string;
  cities: Itinerary[];
  inter_city_legs: RouteLeg[];
  failed_cities: string[];
  warnings: string[];
  cost_usd: number;
}

// ----- run lifecycle --------------------------------------------------------
export type RunStatus = "queued" | "running" | "succeeded" | "failed";
export type RunKind = "plan" | "trip";

export interface RunAccepted {
  run_id: string;
  status: string;
}

export interface RunRecord {
  id: string;
  kind: RunKind;
  status: RunStatus;
  request: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
  warnings: string[];
  cost_usd: number;
  created_at?: string | null;
  updated_at?: string | null;
}

// ----- SSE stream events (union of every shape the /stream endpoint emits) ---
export type RunEvent =
  | { type: "status"; status: RunStatus }
  | { type: "node"; run_id: string; node: string | null; city: string | null; detail: string | null }
  | { type: "done"; run_id?: string; node?: string | null; city?: string | null; detail?: string | null }
  | { type: "failed"; run_id?: string; node?: string | null; city?: string | null; detail?: string | null }
  | { type: "succeeded"; result: Record<string, unknown> | null; error: string | null }
  | { type: "error"; detail: string };

/** The agent pipeline, in execution order — drives the trace timeline skeleton. */
export const AGENT_NODES = ["geocode", "gather", "compose", "critic"] as const;
export type AgentNode = (typeof AGENT_NODES)[number];

export const NODE_LABELS: Record<string, { title: string; blurb: string }> = {
  geocode: { title: "Geocode", blurb: "Resolving cities to real coordinates" },
  gather: { title: "Gather", blurb: "Fetching POIs, weather & retrieval grounding" },
  compose: { title: "Compose", blurb: "Drafting the itinerary with the planner model" },
  critic: { title: "Critic", blurb: "Validating against invented places & gaps" },
};
