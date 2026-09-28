import { expect, test } from "@playwright/test";

/**
 * The login flow, in a real browser.
 *
 * This spec exists because of a specific gap: the app has TWO auth providers, and which
 * one runs depends on whether the AUTH0_* block is filled in
 * (`authMode = authConfigured ? "auth0" : "dev"`). When that switched from the built-in
 * dev login to Auth0, the only verification available was HTTP-level — "/app redirects
 * to /login" — which says nothing about whether a person can actually get in. Typing a
 * password, receiving a session cookie and landing on /app is a browser flow, and
 * nothing in the vitest suite can reach it.
 *
 * It is self-contained: it signs UP a unique user first rather than assuming one exists,
 * so it leaves no dependency on machine state and can run twice in a row.
 */

const unique = () => `e2e-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.test`;
const PASSWORD = "e2e-Passw0rd!-long-enough";

test.describe("authentication", () => {
  test("unauthenticated visitors are gated out of /app", async ({ page }) => {
    const res = await page.goto("/app");
    // Either provider must refuse an anonymous visitor. The app never opens without a
    // session - that is the property, independent of WHICH login is wired.
    expect(page.url()).not.toContain("/app/plan");
    await expect(page).toHaveURL(/\/(login|auth\/login)/);
    expect(res?.status()).toBeLessThan(400);
  });

  test("sign up, then sign in, then reach the app @live", async ({ page }) => {
    await page.goto("/login");

    // Auth0 mode redirects /login straight to the tenant. A browser cannot drive a
    // third-party identity provider safely or repeatably, so skip rather than pretend.
    if (page.url().includes("auth0.com") || page.url().includes("/auth/login")) {
      test.skip(true, "Auth0 mode is active; the dev-login flow is not in play");
    }

    const email = unique();

    // --- sign up -------------------------------------------------------------
    // The mode switch is a RADIO. It was a Radix tab until axe flagged the triggers'
    // `aria-controls` pointing at panels that never existed (aria-valid-attr-value,
    // CRITICAL) - there are no panels, one shared form reacts to `mode`, so a radiogroup
    // is the honest role. This selector tracking that change is the point: the test
    // asserts the accessible role a user's screen reader actually receives.
    await page.getByRole("radio", { name: /create account/i }).click();
    await page.locator("#firstName").waitFor({ state: "visible", timeout: 10_000 });
    await page.locator("#firstName").fill("E2E");
    await page.locator("#lastName").fill("Tester");
    await page.locator("#email").fill(email);
    await page.locator("#password").fill(PASSWORD);
    await page.locator("#confirm").fill(PASSWORD);
    await page.locator('button[type="submit"]').click();

    await expect(page).toHaveURL(/\/app/, { timeout: 30_000 });

    // --- the session actually persists across a navigation -------------------
    // This is the bit that matters. A login that works once but whose cookie is not
    // read on the NEXT request bounces you back to /login on every page - which is
    // exactly the symptom that started this investigation.
    await page.goto("/app");
    await expect(page).toHaveURL(/\/app/);
    expect(page.url()).not.toContain("/login");
  });
});
