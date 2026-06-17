import { NextResponse } from "next/server";

import { BackendError, createTrip } from "@/lib/api";
import type { TripRequest } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<NextResponse> {
  try {
    const body = (await request.json()) as TripRequest;
    const accepted = await createTrip(body);
    return NextResponse.json(accepted, { status: 202 });
  } catch (err) {
    if (err instanceof BackendError) {
      return NextResponse.json({ error: err.message }, { status: err.status });
    }
    return NextResponse.json({ error: "failed to dispatch trip" }, { status: 502 });
  }
}
