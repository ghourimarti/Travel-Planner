import { describe, expect, it } from "vitest";

import { refusalMessage } from "../refusal";

// The BFF forwards the backend body verbatim as `error`.
const body = (detail: string) => JSON.stringify({ detail });

describe("refusalMessage", () => {
  it("names a task-queue outage as transient, not as a switch someone flipped", () => {
    const msg = refusalMessage(503, body("task queue unavailable - please retry shortly"));
    expect(msg).toBe("We couldn't queue your request just now. Please try again in a moment.");
  });

  it("names a database outage as transient too, not as a switch someone flipped", () => {
    const msg = refusalMessage(503, body("database unavailable - please retry shortly"));
    expect(msg).toBe("We couldn't save your request just now. Please try again in a moment.");
  });

  it("keeps the kill-switch wording for every other 503", () => {
    const disabled = "Planning is temporarily disabled. Please try again shortly.";
    expect(refusalMessage(503, body("planning is temporarily disabled"))).toBe(disabled);
    expect(refusalMessage(503)).toBe(disabled);
  });

  it("explains a 429", () => {
    expect(refusalMessage(429, body("rate limit exceeded (tenant_min)"))).toBe(
      "You've hit the rate limit. Please wait a moment.",
    );
  });

  it("falls back to the backend text, then to the bare status", () => {
    expect(refusalMessage(422, "bad input")).toBe("bad input");
    expect(refusalMessage(500)).toBe("Request failed (500).");
  });
});
