import { describe, expect, it } from "vitest";

import { formatUsd, joinCities } from "@/lib/utils";

describe("joinCities", () => {
  it("formats one, two and many cities", () => {
    expect(joinCities(["Tokyo"])).toBe("Tokyo");
    expect(joinCities(["Tokyo", "Kyoto"])).toBe("Tokyo & Kyoto");
    expect(joinCities(["Tokyo", "Kyoto", "Osaka"])).toBe("Tokyo, Kyoto & Osaka");
  });
});

describe("formatUsd", () => {
  it("shows 4dp for sub-cent and 2dp otherwise", () => {
    expect(formatUsd(0.0041)).toBe("$0.0041");
    expect(formatUsd(12.5)).toBe("$12.50");
    expect(formatUsd(null)).toBe("—");
  });
});
