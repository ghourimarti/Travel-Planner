import type { Page } from "@playwright/test";

/** A fresh account per run, so specs never depend on machine state. */
export const uniqueEmail = () =>
  `e2e-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.test`;

export const PASSWORD = "e2e-Passw0rd!-long-enough";

/** True when the app is wired to Auth0 rather than its built-in dev login. */
export async function isAuth0Mode(page: Page): Promise<boolean> {
  await page.goto("/login");
  return page.url().includes("auth0.com") || page.url().includes("/auth/login");
}

/**
 * Sign up and land on /app.
 *
 * Signing UP rather than signing IN is deliberate: it needs no seeded fixture, works on
 * a wiped volume, and can run twice in a row without colliding.
 */
export async function signIn(page: Page): Promise<string> {
  await page.goto("/login");
  const email = uniqueEmail();
  await page.getByRole("radio", { name: /create account/i }).click();
  await page.locator("#firstName").waitFor({ state: "visible", timeout: 15_000 });
  await page.locator("#firstName").fill("E2E");
  await page.locator("#lastName").fill("Tester");
  await page.locator("#email").fill(email);
  await page.locator("#password").fill(PASSWORD);
  await page.locator("#confirm").fill(PASSWORD);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(/\/app/, { timeout: 30_000 });
  return email;
}

/** Routes that must be reachable without a session. */
export const PUBLIC_ROUTES = [
  "/",
  "/about",
  "/features",
  "/pricing",
  "/enterprise",
  "/contact",
  "/privacy",
  "/terms",
  "/login",
  "/signup",
];
