import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TraceTimeline } from "@/components/app/trace-timeline";
import type { NodePhase } from "@/hooks/use-run-stream";

describe("TraceTimeline", () => {
  it("renders all four agent stages and the live status", () => {
    const nodes: Record<string, NodePhase> = {
      geocode: "done",
      gather: "running",
      compose: "pending",
      critic: "pending",
    };
    render(<TraceTimeline nodes={nodes} status="running" />);

    expect(screen.getByText("Geocode")).toBeInTheDocument();
    expect(screen.getByText("Gather")).toBeInTheDocument();
    expect(screen.getByText("Compose")).toBeInTheDocument();
    expect(screen.getByText("Critic")).toBeInTheDocument();
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
