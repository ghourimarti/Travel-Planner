import { randomBytes } from "node:crypto";

import { NextResponse } from "next/server";

import { authMode } from "@/lib/auth";
import { googleAuthUrl, googleConfigured } from "@/lib/google";

export const dynamic = "force-dynamic";

const STATE_COOKIE = "g_oauth_state";

/** Kick off the Google OAuth flow: set a CSRF state cookie, redirect to Google. */
export async function GET(request: Request): Promise<NextResponse> {
  if (authMode === "auth0" || !googleConfigured) {
    return NextResponse.redirect(new URL("/login?error=google_unavailable", request.url));
  }

  const state = randomBytes(16).toString("hex");
  const res = NextResponse.redirect(googleAuthUrl(state));
  res.cookies.set(STATE_COOKIE, state, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 600, // 10 minutes to complete the flow
  });
  return res;
}
