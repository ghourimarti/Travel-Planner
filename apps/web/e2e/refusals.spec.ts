import { execSync } from "node:child_process";

import { expect, test } from "@playwright/test";

import { isAuth0Mode, signIn } from "./_helpers";

/**
 * The refusals besides the kill switch, seen from the BROWSER.
 *
 * The 429 is driven for REAL: the per-tenant minute window is filled in Redis, so the
 * refusal travels API -> BFF -> form exactly as in production, without sending sixty
 * plans - the same technique the playbook uses for the spend key. With auth off, every
 * caller is the synthetic tenant "local" (tp_core.auth.LOCAL_PRINCIPAL).
 *
 * The task-queue and database 503s are MOCKED at the BFF boundary: real ones need Redis or
 * Postgres stopped, and this test's own session depends on both. What is under test is the
 * sentence: an outage must not be reported as a switch somebody flipped.
 *
 * SAFETY: the window key is deleted in `finally` and its absence verified, so a failed
 * run cannot leave the app refusing every plan for up to a minute.
 */

const REDIS = "p3-ai-travel-planner-redis-1";
const API = "p3-ai-travel-planner-api-1";
const WINDOW = "ratelimit:tenant_min:local:60";

function sh(cmd: string): string {
  return execSync(cmd, { stdio: "pipe" }).toString().trim();
}

async function submitPlan(page: import("@playwright/test").Page) {
  await page.goto("/app/plan");
  await page.locator("#city").fill("Kyoto");
  await page.locator('button[type="submit"]').click();
}

test.describe("refusals, from the UI @live", () => {
  test.beforeEach(async ({ page }) => {
    if (await isAuth0Mode(page)) {
      test.skip(true, "Auth0 mode is active; the tenant is not the synthetic 'local'");
    }
    await signIn(page);
  });

  test("a rate-limited plan tells the user to wait", async ({ page }) => {
    // printenv, not `sh -c '...'`: execSync goes through cmd.exe on Windows, where single
    // quotes are not quotes. printenv exits 1 when the var is unset -> treated as 0.
    let limit = 0;
    try {
      limit = Number(sh(`docker exec ${API} printenv RATE_LIMIT_PER_MIN`) || "0");
    } catch {
      limit = 0;
    }
    test.skip(limit <= 0, "RATE_LIMIT_PER_MIN is 0 - the per-minute limit is off");

    try {
      sh(`docker exec ${REDIS} redis-cli set ${WINDOW} ${limit} EX 60`);
      await submitPlan(page);
      await expect(
        page.getByText("You've hit the rate limit. Please wait a moment."),
      ).toBeVisible({ timeout: 30_000 });
    } finally {
      sh(`docker exec ${REDIS} redis-cli del ${WINDOW}`);
    }
    expect(sh(`docker exec ${REDIS} redis-cli exists ${WINDOW}`), "window must be released").toBe(
      "0",
    );
  });

  test("a task-queue outage is not reported as 'disabled'", async ({ page }) => {
    // The BFF forwards the backend body verbatim as `error`.
    const backend = JSON.stringify({ detail: "task queue unavailable - please retry shortly" });
    await page.route("**/api/plan", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: backend }),
      }),
    );
    await submitPlan(page);
    await expect(
      page.getByText("We couldn't queue your request just now. Please try again in a moment."),
    ).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/temporarily disabled/i)).toHaveCount(0);
  });

  test("a database outage is not reported as 'disabled' either", async ({ page }) => {
    // Mocked like the queue case: a real one needs Postgres stopped (infra drill Q16).
    const backend = JSON.stringify({ detail: "database unavailable - please retry shortly" });
    await page.route("**/api/plan", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ error: backend }),
      }),
    );
    await submitPlan(page);
    await expect(
      page.getByText("We couldn't save your request just now. Please try again in a moment."),
    ).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/temporarily disabled/i)).toHaveCount(0);
  });
});
