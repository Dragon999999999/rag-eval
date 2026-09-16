import { describe, it, expect } from "vitest";
import { getMockDashboardSummary, getMockEmptyDashboard, getMockReadyDashboard } from "./mocks";

describe("Dashboard mocks", () => {
  it("returns valid dashboard summary", () => {
    const summary = getMockDashboardSummary();

    expect(summary.resources.targets.total).toBe(3);
    expect(summary.resources.datasets.total).toBe(5);
    expect(summary.resources.tests.total).toBe(12);
    expect(summary.activeRuns.length).toBe(1);
    expect(summary.recentRuns.length).toBe(3);
    expect(summary.latestCompletedRun).toBeTruthy();
    expect(summary.latestComparison).toBeTruthy();
  });

  it("returns empty dashboard for first-use state", () => {
    const summary = getMockEmptyDashboard();

    expect(summary.resources.targets.total).toBe(0);
    expect(summary.resources.datasets.total).toBe(0);
    expect(summary.resources.tests.total).toBe(0);
    expect(summary.activeRuns.length).toBe(0);
    expect(summary.recentRuns.length).toBe(0);
    expect(summary.latestCompletedRun).toBeNull();
    expect(summary.latestComparison).toBeNull();
  });

  it("returns ready dashboard for ready-to-evaluate state", () => {
    const summary = getMockReadyDashboard();

    expect(summary.resources.targets.total).toBe(1);
    expect(summary.resources.datasets.total).toBe(1);
    expect(summary.resources.tests.total).toBe(0);
    expect(summary.activeRuns.length).toBe(0);
    expect(summary.recentRuns.length).toBe(0);
    expect(summary.latestCompletedRun).toBeNull();
    expect(summary.latestComparison).toBeNull();
  });
});
