import { defineConfig, devices } from "@playwright/test";

/**
 * Browser tests against the RUNNING stack, not a mock.
 *
 * The vitest suite covers components in isolation with jsdom. It cannot answer the
 * question that matters most — "can a person actually complete a task in this app" —
 * because nothing there renders a real page, follows a real redirect, or receives a
 * real server-sent event. These do.
 *
 * NO `webServer` BLOCK ON PURPOSE. The app runs in docker compose (`make up-app`), so
 * letting Playwright start its own `next dev` would test a DIFFERENT process than the
 * one being shipped — different env, different build, different port. Point it at the
 * real thing and fail loudly when it is not up.
 *
 *   make up-app          bring the stack up first
 *   make web-e2e         answer kinds + the live run stream
 *   make web-a11y        axe-core over every route
 *   make web-mobile      Pixel-sized viewport
 *   make web-shots       regenerate docs screenshots
 *   make web-ci          everything that does NOT need a live backend
 *
 * Specs that need the API and a model are tagged @live so CI can exclude them with
 * `--grep-invert @live`.
 */
const BASE_URL = process.env.WEB_BASE_URL ?? "http://localhost:3006";

export default defineConfig({
  testDir: "./e2e",
  // A planned itinerary takes ~7-15s end to end (measured: p50 7.3s, p95 14.3s under
  // load), so a 30s default would flake on the @live specs for no good reason.
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false, // the @live specs share one backend and one rate limit budget
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
});
