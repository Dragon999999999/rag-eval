import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MetricSelector } from "./metric-selector";
import { RunProgress } from "./run-progress";
import { SearchableResourceSelect } from "./searchable-resource-select";
import { TestValidationStatus } from "./test-validation-status";
import type { TestMetricsInfo, ValidationResult } from "../test-types";

const metrics: TestMetricsInfo = {
  test_definition_id: "test-1",
  mode: "EXPLICIT",
  selected_metric_ids: ["quality.answer"],
  applicable_metric_ids: ["quality.answer"],
  judge_config: {},
  retrieval_config: {},
  warnings: [],
  metrics: [
    {
      metric_id: "quality.answer",
      version: "1",
      scope: "CASE",
      description: "Answer quality",
      requirements: [],
      applicable: true,
      selected: true,
      unavailable_reason: null,
      parameters: {},
    },
    {
      metric_id: "retrieval.recall",
      version: "1",
      scope: "CASE",
      description: "Retrieval recall",
      requirements: [{ name: "GOLD_EVIDENCE" }],
      applicable: false,
      selected: false,
      unavailable_reason: "The benchmark does not provide gold evidence.",
      parameters: {},
    },
  ],
};

const validation: ValidationResult = {
  valid: false,
  configuration_status: "INCOMPLETE",
  target_valid: true,
  benchmark_valid: false,
  metrics_valid: false,
  resolved_metric_ids: [],
  errors: ["Select a benchmark."],
  warnings: ["Some metrics are unavailable."],
};

describe("test configuration components", () => {
  it("filters a single searchable selection and returns one id", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <SearchableResourceSelect
        label="Benchmark"
        value={null}
        items={[
          { id: "alpha", name: "Alpha benchmark" },
          { id: "beta", name: "Beta benchmark" },
        ]}
        placeholder="Choose one benchmark"
        getId={(item) => item.id}
        getLabel={(item) => item.name}
        onChange={onChange}
      />
    );

    await user.click(screen.getByRole("button", { name: "Choose one benchmark" }));
    await user.type(screen.getByPlaceholderText("Search benchmark..."), "beta");

    expect(
      screen.queryByRole("option", { name: /Alpha benchmark/ })
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("option", { name: /Beta benchmark/ }));
    expect(onChange).toHaveBeenCalledWith("beta");
  });

  it("explains unavailable metrics and supports select-all", async () => {
    const user = userEvent.setup();
    const onSelectAll = vi.fn();

    render(
      <MetricSelector
        metrics={metrics}
        loading={false}
        selected={["quality.answer"]}
        onToggle={vi.fn()}
        onSelectAll={onSelectAll}
        onImport={vi.fn()}
      />
    );

    expect(
      screen.getByRole("checkbox", { name: "Select retrieval.recall" })
    ).toBeDisabled();
    expect(
      screen.getByText("The benchmark does not provide gold evidence.")
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Select all applicable" }));
    expect(onSelectAll).toHaveBeenCalledOnce();
  });

  it("shows backend readiness errors and warnings", () => {
    render(<TestValidationStatus validation={validation} loading={false} />);

    expect(screen.getByText("Not configured / Incomplete")).toBeInTheDocument();
    expect(screen.getByText("Select a benchmark.")).toBeInTheDocument();
    expect(screen.getByText("Some metrics are unavailable.")).toBeInTheDocument();
  });

  it("shows paused progress with a resume control", async () => {
    const user = userEvent.setup();
    const onResume = vi.fn();

    render(
      <RunProgress
        status="PAUSED"
        progress={{
          run_id: "run-1",
          status: "PAUSED",
          status_reason: "Paused by user",
          total_cases: 10,
          complete_cases: 4,
          failed_cases: 1,
          pending_cases: 5,
          running_cases: 0,
          progress_percent: 50,
          started_at: null,
          finished_at: null,
          elapsed_seconds: 12,
        }}
        onResume={onResume}
      />
    );

    expect(screen.getByText("Paused by user")).toBeInTheDocument();
    expect(screen.getByText("50.0%")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Resume/ }));
    expect(onResume).toHaveBeenCalledOnce();
  });
});
