import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useRunStream } from "@/hooks/use-run-stream";

class MockEventSource {
  static instances: MockEventSource[] = [];
  static readonly CLOSED = 2;
  url: string;
  readyState = 0;
  onmessage: ((e: MessageEvent<string>) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }
  close() {
    this.readyState = MockEventSource.CLOSED;
  }
  emit(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent<string>);
  }
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("useRunStream", () => {
  it("advances node phases as 'node' events arrive", () => {
    const { result } = renderHook(() => useRunStream("r1"));
    const es = MockEventSource.instances[0];

    expect(result.current.nodes.geocode).toBe("running");

    act(() => es.emit({ type: "node", run_id: "r1", node: "geocode", city: null, detail: null }));

    expect(result.current.nodes.geocode).toBe("done");
    expect(result.current.nodes.gather).toBe("running");
    expect(result.current.status).toBe("running");
  });

  it("fetches the final record and marks succeeded on 'done'", async () => {
    const record = {
      id: "r1",
      kind: "plan",
      status: "succeeded",
      request: {},
      result: { city: "Tokyo", summary_markdown: "ok", grounded: true, cost_usd: 0.004 },
      error: null,
      warnings: [],
      cost_usd: 0.004,
    };
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(record), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useRunStream("r1"));
    const es = MockEventSource.instances[0];

    act(() => es.emit({ type: "done", run_id: "r1" }));

    await waitFor(() => expect(result.current.status).toBe("succeeded"));
    expect(fetchMock).toHaveBeenCalledWith("/api/runs/r1", expect.anything());
    expect(result.current.record?.result).toMatchObject({ city: "Tokyo" });
    expect(es.readyState).toBe(MockEventSource.CLOSED);
  });
});
