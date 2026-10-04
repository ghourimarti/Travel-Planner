import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

import { PUBLIC_ROUTES } from "./_helpers";

// Scan a STABLE frame. A page caught mid-render or mid-entrance-animation can have text
// at partial opacity, and axe's colour-contrast rule measures exactly that frame: /privacy
// failed 1 run in 4 (2026-09-30) and passed every other time, with no artifact left to
// read. Freezing motion changes nothing a user sees at rest - it only removes the race.
const FREEZE_MOTION = `*, *::before, *::after {
  animation-duration: 0s !important; animation-delay: 0s !important;
  transition-duration: 0s !important; transition-delay: 0s !important;
}`;

async function settle(page: Page) {
  await page.addStyleTag({ content: FREEZE_MOTION });
  // Bounded: a page that never goes network-idle must not hang the gate.
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => undefined);
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
}

/**
 * WCAG 2.1 A/AA via axe-core, on every public route.
 *
 * Accessibility had ZERO coverage before this: nothing in the vitest suite renders a
 * full page, and contrast/landmark/label violations are invisible to a component test
 * by construction.
 *
 * Scoped to `wcag2a`/`wcag2aa` tags rather than every axe rule, so the gate reflects a
 * standard someone can point at instead of one tool's full opinion. Violations are
 * printed with their target selectors — a count alone tells you nothing actionable.
 */

function report(violations: { id: string; impact?: string | null; nodes: { target: unknown[] }[] }[]) {
  return violations
    .map((v) => `  [${v.impact ?? "n/a"}] ${v.id} — ${v.nodes.length} node(s)\n` +
      v.nodes.slice(0, 3).map((n) => `      ${JSON.stringify(n.target)}`).join("\n"))
    .join("\n");
}

test.describe("accessibility", () => {
  for (const route of PUBLIC_ROUTES) {
    test(`${route} has no WCAG A/AA violations`, async ({ page }) => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      const res = await page.goto(route);
      expect(res?.status(), `${route} should render`).toBeLessThan(400);
      await settle(page);

      const { violations } = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();

      // PRINT before asserting. Passing the detail as expect()'s message did not reach
      // the reporter, so the run said "Expected 0, Received 1" and nothing about WHICH
      // rule, WHICH element, or how to fix it - a failure you cannot act on.
      if (violations.length) {
        console.log(`\nAXE VIOLATIONS on ${route}:\n${report(violations)}\n`);
      }
      expect(violations.length, `see AXE VIOLATIONS above for ${route}`).toBe(0);
    });
  }
});
