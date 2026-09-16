/**
 * Dashboard domain types and data contracts.
 *
 * These types represent the frontend's view of dashboard data,
 * decoupled from backend database/ORM structures.
 */

/** Direction semantics for metric deltas */
export type MetricDirection =
  | "higher-is-better"
  | "lower-is-better"
  | "neutral";

/** Run status values */
export type RunStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

/** Resource summary counts */
export interface ResourceSummary {
  targets: {
    total: number;
    secondaryLabel?: string;
  };
  datasets: {
    total: number;
    secondaryLabel?: string;
  };
  tests: {
    total: number;
    secondaryLabel?: string;
  };
}

/** Active run summary for dashboard display */
export interface DashboardRunSummary {
  runId: string;
  testName: string;
  targetName: string;
  datasetName: string;
  status: RunStatus;
  progress: {
    completed: number;
    total: number;
    percent: number;
  };
  metrics?: {
    completed: number;
    failed: number;
    remaining: number;
    running?: number;
  };
  keyMetrics?: DashboardMetric[];
  startedAt: string; // ISO timestamp
  duration?: number; // seconds
}

/** Single metric value for dashboard display */
export interface DashboardMetric {
  metricId: string;
  label: string;
  value: number | string;
  unit?: string;
  delta?: {
    value: number;
    direction: MetricDirection;
  };
}

/** Latest completed run summary */
export interface LatestRunSummary {
  runId: string;
  testName: string;
  targetName: string;
  datasetName: string;
  status: "completed" | "failed";
  metrics: DashboardMetric[];
  startedAt: string;
  completedAt: string;
  duration: number; // seconds
}

/** Metric comparison between runs */
export interface DashboardMetricComparison {
  metricId: string;
  label: string;
  previousValue: number | null;
  currentValue: number | null;
  absoluteDelta: number | null;
  relativeDelta?: number | null;
  direction: MetricDirection;
  unit?: string;
}

/** Run comparison summary */
export interface RunComparisonSummary {
  baselineRunId: string;
  baselineName: string;
  comparisonRunId: string;
  comparisonName: string;
  metrics: DashboardMetricComparison[];
  comparedAt: string;
}

/** Main dashboard summary data contract */
export interface DashboardSummary {
  resources: ResourceSummary;
  activeRuns: DashboardRunSummary[];
  recentRuns: DashboardRunSummary[];
  latestCompletedRun: LatestRunSummary | null;
  latestComparison: RunComparisonSummary | null;
}

/** Dashboard state variants */
export type DashboardState =
  | "loading"
  | "first-use" // No resources at all
  | "ready-to-evaluate" // Resources exist but no runs
  | "operational" // Has run data
  | "error"; // Fetch or data error
