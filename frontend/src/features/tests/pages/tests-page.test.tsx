import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useBenchmarkList } from "@/features/datasets/use-datasets";
import { useTargetList } from "@/features/targets/use-targets";
import { useTests } from "../use-tests";
import { TestsPage } from "./tests-page";

vi.mock("@/features/datasets/use-datasets", () => ({
  useBenchmarkList: vi.fn(),
}));

vi.mock("@/features/targets/use-targets", () => ({
  useTargetList: vi.fn(),
}));

vi.mock("../use-tests", () => ({
  useTests: vi.fn(),
}));

function LocationProbe() {
  return <output data-testid="location">{useLocation().pathname}</output>;
}

const testDefinition = {
  test_definition_id: "test-1",
  name: "Grounding test",
  description: null,
  configuration_status: "READY",
  target_id: "target-1",
  benchmark_id: "benchmark-1",
  metric_selection_mode: "ALL_AVAILABLE",
  judge_config: {},
  retrieval_config: {},
  execution_config: {},
  seed: null,
  tags: [],
  metadata: {},
  definition_hash: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("TestsPage", () => {
  beforeEach(() => {
    vi.mocked(useTests).mockReturnValue({
      data: [testDefinition],
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as never);
    vi.mocked(useBenchmarkList).mockReturnValue({
      data: [
        {
          benchmark_id: "benchmark-1",
          name: "Support benchmark",
        },
      ],
    } as never);
    vi.mocked(useTargetList).mockReturnValue({
      data: [
        {
          target_id: "target-1",
          name: "Production target",
        },
      ],
    } as never);
  });

  function renderPage() {
    return render(
      <MemoryRouter initialEntries={["/tests"]}>
        <TestsPage />
        <LocationProbe />
      </MemoryRouter>
    );
  }

  it("shows benchmark and target names while retaining their ids", () => {
    renderPage();

    expect(screen.getByText("Support benchmark")).toBeInTheDocument();
    expect(screen.getByText("benchmark-1")).toBeInTheDocument();
    expect(screen.getByText("Production target")).toBeInTheDocument();
    expect(screen.getByText("target-1")).toBeInTheDocument();
  });

  it("navigates the row to the test detail page", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByText("test-1"));

    expect(screen.getByTestId("location")).toHaveTextContent("/tests/test-1");
  });

  it("navigates resource links without navigating the row", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("link", { name: "Support benchmark" }));

    expect(screen.getByTestId("location")).toHaveTextContent("/benchmarks/benchmark-1");

    await user.click(screen.getByRole("link", { name: "Production target" }));

    expect(screen.getByTestId("location")).toHaveTextContent("/targets/target-1");
  });
});
