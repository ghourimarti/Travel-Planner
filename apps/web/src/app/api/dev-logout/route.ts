import { NextResponse } from "next/server";

import { DEV_COOKIE_NAME } from "@/lib/auth";

export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<NextResponse> {
  const res = NextResponse.redirect(new URL("/", request.url));
  res.cookies.delete(DEV_COOKIE_NAME);
  return res;
}
