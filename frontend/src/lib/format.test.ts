import { describe, it, expect } from "vitest";
import {
  formatPercent,
  formatDuration,
  formatRelativeTime,
  formatMetricValue,
  formatDelta,
  formatTimestamp,
} from "./format";

describe("formatPercent", () => {
  it("formats decimal as percentage", () => {
    expect(formatPercent(0.912)).toBe("91.2%");
  });

  it("formats with specified decimals", () => {
    expect(formatPercent(0.9123, 2)).toBe("91.23%");
  });

  it("handles zero", () => {
    expect(formatPercent(0)).toBe("0.0%");
  });
});

describe("formatDuration", () => {
  it("formats seconds", () => {
    expect(formatDuration(45)).toBe("45s");
  });

  it("formats minutes and seconds", () => {
    expect(formatDuration(125)).toBe("2m 5s");
  });

  it("formats minutes only", () => {
    expect(formatDuration(120)).toBe("2m");
  });

  it("formats hours and minutes", () => {
    expect(formatDuration(3720)).toBe("1h 2m");
  });
});

describe("formatRelativeTime", () => {
  it("formats recent time", () => {
    const now = new Date().toISOString();
    expect(formatRelativeTime(now)).toBe("just now");
  });

  it("formats minutes ago", () => {
    const fiveMinAgo = new Date(Date.now() - 300000).toISOString();
    expect(formatRelativeTime(fiveMinAgo)).toBe("5m ago");
  });

  it("formats hours ago", () => {
    const threeHoursAgo = new Date(Date.now() - 10800000).toISOString();
    expect(formatRelativeTime(threeHoursAgo)).toBe("3h ago");
  });
});

describe("formatMetricValue", () => {
  it("formats small decimals with precision", () => {
    expect(formatMetricValue(0.9123)).toBe("0.912");
  });

  it("formats larger numbers", () => {
    expect(formatMetricValue(760)).toBe("760.0");
  });

  it("formats with unit", () => {
    expect(formatMetricValue(760, "ms")).toBe("760.0ms");
  });

  it("handles string values", () => {
    expect(formatMetricValue("N/A")).toBe("N/A");
  });
});

describe("formatDelta", () => {
  it("formats positive delta for higher-is-better", () => {
    const result = formatDelta(0.05, "higher-is-better");
    expect(result.text).toBe("+0.1");
    expect(result.isImprovement).toBe(true);
    expect(result.isNeutral).toBe(false);
  });

  it("formats negative delta for higher-is-better", () => {
    const result = formatDelta(-0.05, "higher-is-better");
    expect(result.text).toBe("-0.1");
    expect(result.isImprovement).toBe(false);
  });

  it("formats negative delta for lower-is-better (improvement)", () => {
    const result = formatDelta(-60, "lower-is-better", "ms");
    expect(result.text).toBe("-60.0ms");
    expect(result.isImprovement).toBe(true);
  });

  it("formats neutral direction", () => {
    const result = formatDelta(0.05, "neutral");
    expect(result.isNeutral).toBe(true);
  });
});

describe("formatTimestamp", () => {
  it("formats time", () => {
    const date = new Date("2024-01-15T14:30:00Z");
    expect(formatTimestamp(date.toISOString())).toMatch(/\d{1,2}:\d{2}/);
  });
});
