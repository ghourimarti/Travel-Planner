import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TraceTimeline } from "@/components/app/trace-timeline";
import type { NodePhase } from "@/hooks/use-run-stream";

describe("TraceTimeline", () => {
  it("renders all four planning stages and the live status", () => {
    const nodes: Record<string, NodePhase> = {
      geocode: "done",
      gather: "running",
      compose: "pending",
      critic: "pending",
    };
    render(<TraceTimeline nodes={nodes} status="running" />);

    expect(screen.getByText("Finding your destinations")).toBeInTheDocument();
    expect(screen.getByText("Discovering places")).toBeInTheDocument();
    expect(screen.getByText("Building your itinerary")).toBeInTheDocument();
    expect(screen.getByText("Double-checking everything")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
  });

  it("shows the completed state when the run succeeds", () => {
    const nodes: Record<string, NodePhase> = {
      geocode: "done",
      gather: "done",
      compose: "done",
      critic: "done",
    };
    render(<TraceTimeline nodes={nodes} status="succeeded" />);
    expect(screen.getByText("Complete")).toBeInTheDocument();
  });
});
