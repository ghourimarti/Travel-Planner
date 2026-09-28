import { execSync } from "node:child_process";

import { expect, test } from "@playwright/test";

import { isAuth0Mode, signIn } from "./_helpers";

/**
 * Q9 (docs/INSPECTION.md) seen from the BROWSER, not from curl.
 *
 * The API side is already proven: `make costctl-drill` shows the runtime switch, the
 * static floor and the spend breaker each returning 503, and that Redis cannot lift the
 * floor. None of that says what a PERSON sees. A 503 that the UI renders as a spinner
 * that never stops, or as a blank panel, is a worse outage than the refusal it reports —
 * the operator flipped a switch expecting a clear "temporarily disabled" and the user
 * gets something indistinguishable from the app being broken.
 *
 * A 503 also creates NO run row and the api's counters reset on restart, so there is no
 * durable record of what happened during a real incident. This test is the only way to
 * answer the question after the fact.
 *
 * SAFETY: the switch is released in `finally` AND re-asserted at the end, because a test
 * that leaves planning disabled has caused the outage it was meant to study. That has
 * already happened twice on this project by hand.
 */

const REDIS = "p3-ai-travel-planner-redis-1";

function killSwitch(on: boolean) {
  const cmd = on
    ? `docker exec ${REDIS} redis-cli set planning:enabled 0`
    : `docker exec ${REDIS} redis-cli del planning:enabled`;
  execSync(cmd, { stdio: "pipe" });
}

test.describe("kill switch, from the UI @live", () => {
  test("a disabled planner tells the user, instead of hanging", async ({ page }) => {
    if (await isAuth0Mode(page)) {
      test.skip(true, "Auth0 mode is active; cannot drive a third-party IdP");
    }
    await signIn(page);

    try {
      killSwitch(true);

      await page.goto("/app/plan");
      await page.locator("#city").fill("Kyoto");
      await page.locator('button[type="submit"]').click();

      // SOMETHING legible must appear. Not a spinner forever, not an empty panel.
      // Deliberately broad: the wording is the app's to choose, the REQUIREMENT is that
      // the user is told rather than left waiting.
      const message = page.getByText(
        /disabled|unavailable|try again|temporarily|error|something went wrong/i,
      );
      await expect(message.first()).toBeVisible({ timeout: 30_000 });
    } finally {
      killSwitch(false);
    }

    // The switch is really back off - verified, not assumed.
    const state = execSync(`docker exec ${REDIS} redis-cli get planning:enabled`, {
      stdio: "pipe",
    })
      .toString()
      .trim();
    expect(state, "kill switch must be released").toBe("");
  });
});
