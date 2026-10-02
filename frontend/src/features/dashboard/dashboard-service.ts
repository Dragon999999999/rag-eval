/** Compose the dashboard from the persisted resource and run APIs. */

import { BenchmarkService } from "@/features/datasets/dataset-service";
import { RunService } from "@/features/results/run-service";
import type { AggregateResultDetail, RunSummary } from "@/features/results/run-types";
import { TargetService } from "@/features/targets/target-service";
import { TestService } from "@/features/tests/test-service";
import type {
  DashboardMetric,
  DashboardRunSummary,
  DashboardSummary,
  LatestRunSummary,
  RunComparisonSummary,
  RunStatus,
} from "./dashboard-types";

function metricLabel(metricId: string): string {
  return (metricId.split(".").at(-1) ?? metricId)
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function displayMetricValue(value: unknown): number | string {
  if (typeof value === "number" || typeof value === "string") return value;
  if (value === null || value === undefined) return "—";
  return JSON.stringify(value);
}

function metricValues(aggregates: AggregateResultDetail[]): DashboardMetric[] {
  return aggregates
    .filter(
      (aggregate) =>
        aggregate.status.toUpperCase() === "COMPUTED" && aggregate.value != null
    )
    .slice(0, 4)
    .map((aggregate) => ({
      metricId: aggregate.metric_id,
      label: metricLabel(aggregate.metric_id),
      value: displayMetricValue(aggregate.value),
    }));
}

function isCompleted(run: RunSummary): boolean {
  return ["COMPLETE", "COMPLETED", "COMPLETED_WITH_ERRORS"].includes(
    run.status.toUpperCase()
  );
}

function isActive(run: RunSummary): boolean {
  return ["PENDING", "CREATED", "RUNNING", "PAUSING", "PAUSED"].includes(
    run.status.toUpperCase()
  );
}

function dashboardStatus(status: string): RunStatus {
  switch (status.toUpperCase()) {
    case "PENDING":
    case "CREATED":
      return "queued";
    case "RUNNING":
    case "PAUSING":
    case "PAUSED":
      return "running";
    case "COMPLETE":
    case "COMPLETED":
      return "completed";
    case "FAILED":
    case "COMPLETED_WITH_ERRORS":
      return "failed";
    default:
      return "cancelled";
  }
}

function runProgress(run: RunSummary): {
  completed: number;
  total: number;
  failed: number;
  remaining: number;
  running: number;
  percent: number;
} {
  const completed = run.complete_cases ?? 0;
  const failed = run.failed_cases ?? 0;
  const total = run.total_cases ?? completed + failed + (run.pending_cases ?? 0);
  const pending = run.pending_cases ?? Math.max(total - completed - failed, 0);
  const percent = run.progress_percent ?? (total > 0 ? (completed / total) * 100 : 0);

  return {
    completed,
    total,
    failed,
    remaining: pending,
    running: Math.max(total - completed - failed - pending, 0),
    percent,
  };
}

function runDuration(run: RunSummary): number | undefined {
  if (!run.started_at) return undefined;
  const end = run.finished_at ? new Date(run.finished_at) : new Date();
  return Math.max((end.getTime() - new Date(run.started_at).getTime()) / 1000, 0);
}

function toDashboardRun(
  run: RunSummary,
  targetNames: Map<string, string>,
  benchmarkNames: Map<string, string>,
  testNames: Map<string, string>,
  aggregates: AggregateResultDetail[] = []
): DashboardRunSummary {
  const progress = runProgress(run);
  return {
    runId: run.run_id,
    testName: testNames.get(run.test_definition_id ?? "") ?? run.name,
    targetName: targetNames.get(run.target_id ?? "") ?? run.target_id ?? "—",
    datasetName: benchmarkNames.get(run.benchmark_id ?? "") ?? run.benchmark_id ?? "—",
    status: dashboardStatus(run.status),
    progress: {
      completed: progress.completed,
      total: progress.total,
      percent: progress.percent,
    },
    metrics: {
      completed: progress.completed,
      failed: progress.failed,
      remaining: progress.remaining,
      running: progress.running,
    },
    keyMetrics: metricValues(aggregates),
    startedAt: run.started_at ?? run.created_at,
    duration: runDuration(run),
  };
}

function comparisonMetrics(
  baseline: AggregateResultDetail[],
  current: AggregateResultDetail[]
): RunComparisonSummary["metrics"] {
  const baselineByKey = new Map(
    baseline.map((item) => [
      `${item.metric_id}:${item.metric_version}:${item.aggregation}`,
      item,
    ])
  );
  const currentByKey = new Map(
    current.map((item) => [
      `${item.metric_id}:${item.metric_version}:${item.aggregation}`,
      item,
    ])
  );
  const keys = new Set([...baselineByKey.keys(), ...currentByKey.keys()]);

  return [...keys].map((key) => {
    const previous = baselineByKey.get(key);
    const currentValue = currentByKey.get(key);
    const previousNumber = typeof previous?.value === "number" ? previous.value : null;
    const currentNumber =
      typeof currentValue?.value === "number" ? currentValue.value : null;
    const absoluteDelta =
      previousNumber !== null && currentNumber !== null
        ? currentNumber - previousNumber
        : null;

    return {
      metricId: currentValue?.metric_id ?? previous?.metric_id ?? key,
      label: metricLabel(currentValue?.metric_id ?? previous?.metric_id ?? key),
      previousValue: previousNumber,
      currentValue: currentNumber,
      absoluteDelta,
      relativeDelta:
        absoluteDelta !== null && previousNumber !== null && previousNumber !== 0
          ? (absoluteDelta / previousNumber) * 100
          : null,
      direction: "neutral" as const,
    };
  });
}

async function loadAggregates(
  runs: RunSummary[]
): Promise<Map<string, AggregateResultDetail[]>> {
  const entries = await Promise.all(
    runs.map(async (run) => {
      try {
        const results = await RunService.getRunResults(run.run_id);
        return [run.run_id, results.aggregates] as const;
      } catch {
        // A run can exist before results are persisted. Keep the dashboard
        // useful while that run is still progressing or being recovered.
        return [run.run_id, [] as AggregateResultDetail[]] as const;
      }
    })
  );
  return new Map(entries);
}

function latestRunSummary(
  run: RunSummary,
  aggregates: AggregateResultDetail[],
  targetNames: Map<string, string>,
  benchmarkNames: Map<string, string>,
  testNames: Map<string, string>
): LatestRunSummary {
  const startedAt = run.started_at ?? run.created_at;
  return {
    runId: run.run_id,
    testName: testNames.get(run.test_definition_id ?? "") ?? run.name,
    targetName: targetNames.get(run.target_id ?? "") ?? run.target_id ?? "—",
    datasetName: benchmarkNames.get(run.benchmark_id ?? "") ?? run.benchmark_id ?? "—",
    status: run.status.toUpperCase() === "COMPLETE" ? "completed" : "failed",
    metrics: metricValues(aggregates),
    startedAt,
    completedAt: run.finished_at ?? startedAt,
    duration: runDuration(run) ?? 0,
  };
}

/** Fetch and compose live dashboard data from the persisted resource APIs. */
export async function getDashboardSummary(): Promise<DashboardSummary> {
  const [targets, benchmarks, tests, runs] = await Promise.all([
    TargetService.listTargets(),
    BenchmarkService.listBenchmarks(),
    TestService.listTests(),
    RunService.listRuns({ limit: 50, offset: 0 }),
  ]);

  const targetNames = new Map(targets.map((target) => [target.target_id, target.name]));
  const benchmarkNames = new Map(
    benchmarks.map((benchmark) => [benchmark.benchmark_id, benchmark.name])
  );
  const testNames = new Map(tests.map((test) => [test.test_definition_id, test.name]));
  const completedRuns = runs.filter(isCompleted);
  const activeRuns = runs.filter(isActive);
  const aggregatesByRun = await loadAggregates(completedRuns.slice(0, 2));
  const latest = completedRuns[0];
  const previous = completedRuns[1];

  const totalCases = benchmarks.reduce(
    (total, benchmark) => total + benchmark.case_count,
    0
  );
  const connectedTargets = targets.filter(
    (target) => target.connection_status === "connected"
  ).length;
  const readyTests = tests.filter(
    (test) => test.configuration_status === "READY"
  ).length;

  return {
    resources: {
      targets: {
        total: targets.length,
        secondaryLabel: connectedTargets
          ? `${String(connectedTargets)} connected`
          : undefined,
      },
      datasets: {
        total: benchmarks.length,
        secondaryLabel: totalCases ? `${String(totalCases)} cases` : undefined,
      },
      tests: {
        total: tests.length,
        secondaryLabel: readyTests ? `${String(readyTests)} ready` : undefined,
      },
    },
    activeRuns: activeRuns.map((run) =>
      toDashboardRun(
        run,
        targetNames,
        benchmarkNames,
        testNames,
        aggregatesByRun.get(run.run_id) ?? []
      )
    ),
    recentRuns: runs
      .slice(0, 8)
      .map((run) =>
        toDashboardRun(
          run,
          targetNames,
          benchmarkNames,
          testNames,
          aggregatesByRun.get(run.run_id) ?? []
        )
      ),
    latestCompletedRun: latest
      ? latestRunSummary(
          latest,
          aggregatesByRun.get(latest.run_id) ?? [],
          targetNames,
          benchmarkNames,
          testNames
        )
      : null,
    latestComparison:
      latest && previous
        ? {
            baselineRunId: previous.run_id,
            baselineName: previous.name,
            comparisonRunId: latest.run_id,
            comparisonName: latest.name,
            metrics: comparisonMetrics(
              aggregatesByRun.get(previous.run_id) ?? [],
              aggregatesByRun.get(latest.run_id) ?? []
            ),
            comparedAt: new Date().toISOString(),
          }
        : null,
  };
}
