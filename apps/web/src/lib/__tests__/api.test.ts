import { afterEach, describe, expect, it, vi } from "vitest";

// Avoid pulling the real Auth0/Next server chain into the unit test.
vi.mock("@/lib/auth0", () => ({ backendAuthHeader: async () => ({}) }));

import { BackendError, backendUrl, createPlan, getRun } from "@/lib/api";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("backendUrl", () => {
  it("joins the base and strips a trailing slash", () => {
    vi.stubEnv("BACKEND_API_URL", "http://api.test/");
    expect(backendUrl("/plan")).toBe("http://api.test/plan");
  });
});

describe("createPlan", () => {
  it("POSTs and returns the accepted run", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ run_id: "r1", status: "queued" }), { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);

    const out = await createPlan({ city: "Tokyo", interests: ["food"], days: 2 });

    expect(out.run_id).toBe("r1");
    expect(fetchMock).toHaveBeenCalledOnce();
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.method).toBe("POST");
  });

  it("throws a BackendError carrying the status on a non-2xx", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("disabled", { status: 503 })));
    await expect(createPlan({ city: "X", interests: ["a"], days: 1 })).rejects.toMatchObject({
      name: "BackendError",
      status: 503,
    });
  });
});

describe("getRun", () => {
  it("returns the run record", async () => {
    const record = { id: "r1", kind: "plan", status: "succeeded", request: {}, result: null, error: null, warnings: [], cost_usd: 0 };
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(record), { status: 200 })));
    const out = await getRun("r1");
    expect(out.status).toBe("succeeded");
  });

  it("propagates a BackendError instance", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("nope", { status: 404 })));
    await expect(getRun("missing")).rejects.toBeInstanceOf(BackendError);
  });
});
