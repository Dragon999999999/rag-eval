import { describe, expect, it } from "vitest";
import {
  formatMetricStatistic,
  formatMetricValue,
  getMetricDisplayName,
  getMetricStatistics,
  isMetricStatisticAllowed,
} from "./run-formatters";

describe("metric catalog", () => {
  it("provides an unambiguous human label and unit for usage metrics", () => {
    expect(getMetricDisplayName("usage.total_tokens")).toBe("Usage · Total tokens");
    expect(formatMetricValue(14873, "usage.total_tokens", "sum")).toBe("14,873 tok");
    expect(formatMetricStatistic("median")).toBe("Median");
  });

  it("formats rates as percentages without allowing meaningless sums", () => {
    expect(formatMetricValue(0.75, "reliability.availability", "mean")).toBe("75.0%");
    expect(isMetricStatisticAllowed("reliability.error_rate", "sum")).toBe(false);
    expect(isMetricStatisticAllowed("reliability.error_rate", "p95")).toBe(true);
    expect(getMetricStatistics(["reliability.error_rate"])).not.toContain("sum");
  });

  it("formats latency with its declared unit", () => {
    expect(formatMetricValue(1952, "performance.total_latency_ms", "p95")).toBe(
      "1,952 ms"
    );
  });
});
