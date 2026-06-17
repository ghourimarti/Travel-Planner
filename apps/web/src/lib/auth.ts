/**
 * Unified, fail-closed auth (S13a-auth). Two providers behind one interface:
 *   • Auth0  — used when the AUTH0_* env block is present (production).
 *   • Dev    — a built-in sign-up / sign-in backed by a hashed-password user
 *              store (lib/dev-users), with a `jose`-signed session cookie, so
 *              the app is GATED even without an Auth0 tenant.
 *
 * The app never opens without a session: `getCurrentUser()` returns null until
 * the user signs in, and protected layouts redirect to `loginPath`.
 */
import "server-only";

import { SignJWT, jwtVerify } from "jose";
import { cookies } from "next/headers";

import { authConfigured, getSessionUser as getAuth0User } from "@/lib/auth0";
import { createDevUser, verifyDevUser } from "@/lib/dev-users";
import type { AppUser } from "@/lib/types";

export type AuthMode = "auth0" | "dev";
export const authMode: AuthMode = authConfigured ? "auth0" : "dev";

export const DEV_COOKIE_NAME = "voyantra_dev_session";

export const loginPath = authMode === "auth0" ? "/auth/login?returnTo=/app" : "/login";
export const signupPath =
  authMode === "auth0" ? "/auth/login?returnTo=/app&screen_hint=signup" : "/signup";
export const logoutPath = authMode === "auth0" ? "/auth/logout" : "/api/dev-logout";

export interface DevAuthResult {
  name: string;
  email: string;
}

function sessionSecret(): Uint8Array {
  const secret =
    process.env.SESSION_SECRET ?? process.env.AUTH0_SECRET ?? "voyantra-dev-insecure-secret";
  return new TextEncoder().encode(secret);
}

export async function createDevSession(email: string, name?: string): Promise<string> {
  return new SignJWT({ name: name ?? email.split("@")[0], email })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(`dev|${email}`)
    .setIssuedAt()
    .setExpirationTime("7d")
    .sign(sessionSecret());
}

/** Sign in: check the user store, then fall back to the shared demo password. */
export async function verifyDevLogin(email: string, password: string): Promise<DevAuthResult | null> {
  const user = await verifyDevUser(email, password);
  if (user) return { name: user.name, email: user.email };

  // Quick-demo fallback: any email + DEV_LOGIN_PASSWORD (default "voyantra").
  const expected = process.env.DEV_LOGIN_PASSWORD ?? "voyantra";
  if (email.trim() && password === expected) {
    const e = email.trim();
    return { name: e.split("@")[0], email: e };
  }
  return null;
}

/** Sign up: create a hashed-password account, with basic validation. */
export async function registerDevUser(
  name: string,
  email: string,
  password: string,
): Promise<DevAuthResult | { error: string }> {
  if (!email.trim()) return { error: "Email is required." };
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) return { error: "Enter a valid email." };
  if ((password ?? "").length < 6) return { error: "Password must be at least 6 characters." };

  const res = await createDevUser({ name, email, password });
  if ("error" in res) return res;
  return { name: res.name, email: res.email };
}

async function getDevUser(): Promise<AppUser | null> {
  const token = (await cookies()).get(DEV_COOKIE_NAME)?.value;
  if (!token) return null;
  try {
    const { payload } = await jwtVerify(token, sessionSecret());
    return {
      sub: String(payload.sub),
      name: typeof payload.name === "string" ? payload.name : undefined,
      email: typeof payload.email === "string" ? payload.email : undefined,
    };
  } catch {
    return null;
  }
}

/** Current user from the active provider, or null. Never throws. */
export async function getCurrentUser(): Promise<AppUser | null> {
  if (authMode === "auth0") {
    const u = await getAuth0User();
    return u ? { sub: u.sub ?? "", name: u.name, email: u.email } : null;
  }
  return getDevUser();
}
