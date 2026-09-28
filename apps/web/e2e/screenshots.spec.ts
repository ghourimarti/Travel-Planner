import path from "node:path";

import { expect, test } from "@playwright/test";

/**
 * Regenerate the documentation screenshots, light and dark.
 *
 * These are ARTEFACTS, not assertions - the app is a portfolio piece and its README
 * needs current images. They are kept in a spec so they are produced by the same
 * browser, viewport and theme mechanism every time, instead of by hand at whatever
 * window size someone happened to have open.
 *
 * Theme: next-themes with attribute="class", so the switch is localStorage `theme` read
 * before hydration. Setting it with addInitScript avoids a flash of the wrong theme
 * being captured, which is what makes hand-taken dark screenshots look wrong.
 */

// `__dirname` does not exist in this ESM package - referencing it made Playwright
// report "No tests found", which reads like a glob problem rather than a ReferenceError
// thrown while loading the module. Playwright runs from the config directory
// (apps/web), so resolve from there.
const OUT = path.resolve(process.cwd(), "../../docs/screenshots");

const PAGES: [name: string, route: string][] = [
  ["home", "/"],
  ["features", "/features"],
  ["pricing", "/pricing"],
  ["enterprise", "/enterprise"],
  ["login", "/login"],
];

for (const theme of ["light", "dark"] as const) {
  test.describe(`screenshots (${theme})`, () => {
    test.use({ viewport: { width: 1440, height: 900 } });

    for (const [name, route] of PAGES) {
      test(`${name} @shots`, async ({ page }, testInfo) => {
        test.skip(testInfo.project.name !== "chromium", "desktop only");

        await page.addInitScript((t) => {
          window.localStorage.setItem("theme", t);
        }, theme);

        const res = await page.goto(route);
        expect(res?.status(), `${route} should render`).toBeLessThan(400);

        // next-themes applies the class after hydration; wait for it rather than
        // sleeping, so a slow machine cannot capture the wrong theme.
        await page.waitForFunction(
          (t) =>
            t === "dark"
              ? document.documentElement.classList.contains("dark")
              : !document.documentElement.classList.contains("dark"),
          theme,
          { timeout: 10_000 },
        );
        await page.waitForLoadState("networkidle");

        await page.screenshot({
          path: path.join(OUT, `${name}-${theme}.png`),
          fullPage: true,
        });
      });
    }
  });
}
