import { expect, test } from "@playwright/test";

import { PUBLIC_ROUTES } from "./_helpers";

/**
 * Mobile layout, on a Pixel 7 viewport (412x915).
 *
 * Run with `--project=mobile`. Mobile had ZERO coverage: jsdom has no viewport, so a
 * component test cannot notice that something overflows the screen.
 *
 * The assertion is deliberately narrow and objective — HORIZONTAL OVERFLOW — rather
 * than a pile of pixel snapshots that break on every copy edit. A page wider than the
 * device is the one mobile bug that is unambiguous, universally bad, and invisible in
 * every other test in this repo.
 */

test.describe("mobile layout", () => {
  for (const route of PUBLIC_ROUTES) {
    test(`${route} does not scroll horizontally`, async ({ page }, testInfo) => {
      test.skip(testInfo.project.name !== "mobile", "mobile project only");

      const res = await page.goto(route);
      expect(res?.status(), `${route} should render`).toBeLessThan(400);

      const { scrollWidth, clientWidth } = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }));

      // A few px of slack: sub-pixel rounding and scrollbar gutters are not bugs.
      expect(
        scrollWidth,
        `${route} overflows by ${scrollWidth - clientWidth}px at ${clientWidth}px wide`,
      ).toBeLessThanOrEqual(clientWidth + 2);
    });
  }

  test("the primary nav is reachable on a phone", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "mobile", "mobile project only");
    await page.goto("/");
    // Either a visible nav or a disclosure control must exist - a site whose navigation
    // is simply absent below a breakpoint is not responsive, it is broken.
    const nav = page.locator("nav, header").first();
    await expect(nav).toBeVisible();
  });
});
