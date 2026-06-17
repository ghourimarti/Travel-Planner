import { NextResponse } from "next/server";

import { BackendError, createPlan } from "@/lib/api";
import type { PlanRequest } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<NextResponse> {
  try {
    const body = (await request.json()) as PlanRequest;
    const accepted = await createPlan(body);
    return NextResponse.json(accepted, { status: 202 });
  } catch (err) {
    if (err instanceof BackendError) {
      return NextResponse.json({ error: err.message }, { status: err.status });
    }
    return NextResponse.json({ error: "failed to dispatch plan" }, { status: 502 });
  }
}
