// k6 load test — exercises the ~50-concurrent target end-to-end.
//
// Service targets encoded as thresholds: dispatch (202) is a lightweight endpoint (p95 < 150ms);
// full async itinerary latency p50 20s / p95 45s (measured by polling the run to terminal).
// "Demonstrated scale" = ~50 concurrent here; the capacity model argues the path to 500.
//
// Run:  BASE_URL=http://localhost:8000 [TOKEN=<jwt>] k6 run tests/load/plan_smoke.js
// Needs the API + a worker + backing services up (make services && make api && make worker).
import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Rate } from "k6/metrics";

const BASE = __ENV.BASE_URL || "http://localhost:8000";
const TOKEN = __ENV.TOKEN || "";
const HEADERS = {
  "Content-Type": "application/json",
  ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
};

const e2e = new Trend("itinerary_e2e_seconds", true);
const completed = new Rate("itinerary_completed");

export const options = {
  scenarios: {
    ramp_to_50_concurrent: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 10 },
        { duration: "1m", target: 50 }, // the demonstrated-scale target
        { duration: "2m", target: 50 },
        { duration: "30s", target: 0 },
      ],
      gracefulStop: "90s",
    },
  },
  thresholds: {
    "http_req_duration{endpoint:dispatch}": ["p(95)<150"], // lightweight endpoint NFR
    itinerary_e2e_seconds: ["p(50)<20", "p(95)<45"], // full-itinerary latency NFR
    itinerary_completed: ["rate>0.99"], // ≥99% of runs reach a terminal state
  },
};

const CITIES = ["Tokyo", "Kyoto", "Osaka", "Paris", "Rome", "Lisbon", "Hanoi"];

export default function () {
  const body = JSON.stringify({
    city: CITIES[Math.floor(Math.random() * CITIES.length)],
    interests: ["temples", "food"],
  });
  const start = Date.now();

  const res = http.post(`${BASE}/plan`, body, {
    headers: HEADERS,
    tags: { endpoint: "dispatch" },
  });
  if (!check(res, { "dispatch 202": (r) => r.status === 202 })) {
    completed.add(false);
    return;
  }
  const runId = res.json("run_id");

  // Poll to terminal (succeeded/failed), measuring true end-to-end latency.
  for (let i = 0; i < 60; i++) {
    sleep(1);
    const s = http.get(`${BASE}/runs/${runId}`, { headers: HEADERS, tags: { endpoint: "status" } });
    if (s.status !== 200) continue;
    const status = s.json("status");
    if (status === "succeeded" || status === "failed") {
      e2e.add((Date.now() - start) / 1000);
      completed.add(status === "succeeded");
      return;
    }
  }
  completed.add(false); // never reached terminal within the poll budget
}
