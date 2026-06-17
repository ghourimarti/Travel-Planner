import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { auth0 } from "@/lib/auth0";

/**
 * When Auth0 is configured, its middleware mounts /auth/login, /auth/logout and
 * /auth/callback and refreshes the session cookie. When it isn't (keyless dev),
 * we pass every request straight through so the app still works.
 */
export async function middleware(request: NextRequest): Promise<NextResponse> {
  if (!auth0) return NextResponse.next();
  return auth0.middleware(request);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
