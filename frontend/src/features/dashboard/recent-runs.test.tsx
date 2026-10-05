import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { RecentRuns } from "./recent-runs";
import type { DashboardRunSummary } from "./dashboard-types";

function LocationProbe() {
  return <output data-testid="location">{useLocation().pathname}</output>;
}

const run: DashboardRunSummary = {
  runId: "run-1",
  testName: "Grounding test",
  targetId: "target-1",
  targetName: "Production target",
  benchmarkId: "benchmark-1",
  datasetName: "Support benchmark",
  status: "completed",
  progress: { completed: 10, total: 10, percent: 100 },
  keyMetrics: [],
  startedAt: "2026-01-01T00:00:00Z",
};

function renderRecentRuns() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <RecentRuns runs={[run]} />
      <LocationProbe />
    </MemoryRouter>
  );
}

describe("RecentRuns", () => {
  it("navigates the row to the run detail page", async () => {
    const user = userEvent.setup();
    renderRecentRuns();

    await user.click(screen.getByText("Completed"));

    expect(screen.getByTestId("location")).toHaveTextContent("/runs/run-1");
  });

  it("navigates benchmark and target links independently", async () => {
    const user = userEvent.setup();
    renderRecentRuns();

    await user.click(screen.getByRole("link", { name: "Support benchmark" }));
    expect(screen.getByTestId("location")).toHaveTextContent("/benchmarks/benchmark-1");

    await user.click(screen.getByRole("link", { name: "Production target" }));
    expect(screen.getByTestId("location")).toHaveTextContent("/targets/target-1");
  });
});
