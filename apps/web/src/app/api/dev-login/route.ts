import { NextResponse } from "next/server";

import { DEV_COOKIE_NAME, authMode, createDevSession, verifyDevLogin } from "@/lib/auth";

export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<NextResponse> {
  if (authMode === "auth0") {
    return NextResponse.json({ error: "dev login disabled" }, { status: 404 });
  }

  let email = "";
  let password = "";
  try {
    const body = (await request.json()) as { email?: string; password?: string };
    email = body.email ?? "";
    password = body.password ?? "";
  } catch {
    return NextResponse.json({ error: "invalid request" }, { status: 400 });
  }

  const result = await verifyDevLogin(email, password);
  if (!result) {
    return NextResponse.json({ error: "Invalid email or password." }, { status: 401 });
  }

  const token = await createDevSession(result.email, result.name);
  const res = NextResponse.json({ ok: true });
  res.cookies.set(DEV_COOKIE_NAME, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  return res;
}
