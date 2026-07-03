import { NextResponse } from "next/server";

import { DEV_COOKIE_NAME, authMode, createDevSession } from "@/lib/auth";
import { exchangeCodeForProfile, googleConfigured } from "@/lib/google";

export const dynamic = "force-dynamic";

const STATE_COOKIE = "g_oauth_state";

/** Google redirects here with ?code&state. Validate, exchange, then mint our own session. */
export async function GET(request: Request): Promise<NextResponse> {
  const url = new URL(request.url);
  const fail = (reason: string) =>
    NextResponse.redirect(new URL(`/login?error=${reason}`, request.url));

  if (authMode === "auth0" || !googleConfigured) return fail("google_unavailable");

  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const expectedState = request.headers
    .get("cookie")
    ?.split(";")
    .map((c) => c.trim())
    .find((c) => c.startsWith(`${STATE_COOKIE}=`))
    ?.slice(STATE_COOKIE.length + 1);

  if (!code || !state || !expectedState || state !== expectedState) {
    return fail("google_state");
  }

  const profile = await exchangeCodeForProfile(code);
  if (!profile) return fail("google_failed");

  const token = await createDevSession(profile.email, profile.name);
  const res = NextResponse.redirect(new URL("/app", request.url));
  res.cookies.set(DEV_COOKIE_NAME, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  res.cookies.delete(STATE_COOKIE);
  return res;
}
