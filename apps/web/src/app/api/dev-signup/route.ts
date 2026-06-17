import { NextResponse } from "next/server";

import { DEV_COOKIE_NAME, authMode, createDevSession, registerDevUser } from "@/lib/auth";

export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<NextResponse> {
  if (authMode === "auth0") {
    return NextResponse.json({ error: "dev signup disabled" }, { status: 404 });
  }

  let name = "";
  let email = "";
  let password = "";
  try {
    const body = (await request.json()) as { name?: string; email?: string; password?: string };
    name = body.name ?? "";
    email = body.email ?? "";
    password = body.password ?? "";
  } catch {
    return NextResponse.json({ error: "invalid request" }, { status: 400 });
  }

  const result = await registerDevUser(name, email, password);
  if ("error" in result) {
    // 409 when the email is taken, 400 for validation problems.
    const status = result.error.includes("already exists") ? 409 : 400;
    return NextResponse.json({ error: result.error }, { status });
  }

  const token = await createDevSession(result.email, result.name);
  const res = NextResponse.json({ ok: true }, { status: 201 });
  res.cookies.set(DEV_COOKIE_NAME, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  return res;
}
