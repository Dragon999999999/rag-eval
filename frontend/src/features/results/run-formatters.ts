/**
 * Formatting utilities for run/case/metric display.
 */
import type {
  RunStatus,
  CaseStatus,
  AttemptStatus,
  MetricStatus,
  RunProgress,
  AggregateResultSummary,
} from "./run-types";
import { formatCatalogMetricValue } from "./metric-catalog";

/**
 * Format run status for display.
 */
export function formatRunStatus(status: RunStatus): string {
  return status
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (value) => value.toUpperCase());
}

/**
 * Get status badge variant for run status.
 */
export function getRunStatusVariant(
  status: RunStatus
): "success" | "warning" | "error" | "info" | "neutral" {
  switch (status.toUpperCase()) {
    case "COMPLETE":
    case "COMPLETED":
      return "success";
    case "COMPLETED_WITH_ERRORS":
      return "warning";
    case "RUNNING":
    case "PENDING":
    case "PAUSING":
    case "PAUSED":
      return "info";
    case "FAILED":
      return "error";
    case "CANCELLED":
      return "neutral";
    default:
      return "neutral";
  }
}

/** Format a backend case lifecycle value. */
export function formatCaseStatus(status: CaseStatus): string {
  return status
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (value) => value.toUpperCase());
}

/** Get the badge variant for a case lifecycle value. */
export function getCaseStatusVariant(
  status: CaseStatus
): "success" | "warning" | "error" | "info" | "neutral" {
  switch (status.toUpperCase()) {
    case "COMPLETE":
      return "success";
    case "RUNNING":
    case "PENDING":
      return "info";
    case "FAILED":
      return "error";
    case "TARGET_COMPLETE":
    case "INTERRUPTED":
      return "warning";
    default:
      return "neutral";
  }
}

/**
 * Format attempt status for display.
 */
export function formatAttemptStatus(status: AttemptStatus): string {
  return status
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (value) => value.toUpperCase());
}

/**
 * Format metric status for display.
 */
export function formatMetricStatus(status: MetricStatus): string {
  switch (status.toUpperCase()) {
    case "COMPUTED":
      return "Computed";
    case "UNAVAILABLE_MISSING_INPUT":
      return "Unavailable";
    case "NOT_APPLICABLE":
      return "N/A";
    case "FAILED":
      return "Failed";
    case "SKIPPED":
      return "Skipped";
    default:
      return "Unknown";
  }
}

/**
 * Format progress percentage.
 */
export function formatProgress(progress: RunProgress | null | undefined): string {
  if (!progress) return "No data";
  return `${String(progress.complete_cases)}/${String(progress.total_cases)} (${progress.progress_percent.toFixed(0)}%)`;
}

/**
 * Format elapsed time in human-readable format.
 */
export function formatElapsedTime(seconds: number | null): string {
  if (seconds == null) return "—";

  if (seconds < 60) {
    return `${String(Math.round(seconds))}s`;
  }

  if (seconds < 3600) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${String(mins)}m ${String(secs)}s`;
  }

  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${String(hours)}h ${String(mins)}m`;
}

/**
 * Format relative time for display.
 */
export function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return "—";

  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins.toFixed(0)}m ago`;
  if (diffHours < 24) return `${diffHours.toFixed(0)}h ago`;
  if (diffDays < 7) return `${diffDays.toFixed(0)}d ago`;

  return date.toLocaleDateString();
}

/**
 * Format metric value with appropriate precision.
 */
export function formatMetricValue(
  value: unknown,
  metricId?: string,
  statistic?: string
): string {
  if (metricId === "ms") {
    return typeof value === "number" ? `${value.toFixed(1)}ms` : String(value);
  }
  return formatCatalogMetricValue(value, metricId, statistic);
}

/**
 * Format metric delta for comparison.
 */
export function formatMetricDelta(
  delta: number | null,
  _direction: "higher_is_better" | "lower_is_better" | "neutral",
  relativePercent: number | null = null
): string {
  if (delta == null) return "—";

  const sign = delta > 0 ? "+" : "";
  const deltaStr =
    typeof delta === "number" ? `${sign}${delta.toFixed(3)}` : String(delta);

  if (relativePercent != null) {
    const relSign = relativePercent > 0 ? "+" : "";
    return `${deltaStr} (${relSign}${relativePercent.toFixed(1)}%)`;
  }

  return deltaStr;
}

/**
 * Get delta variant based on value.
 * Note: direction parameter is reserved for future use when delta interpretation depends on metric semantics.
 */
export function getDeltaVariant(
  delta: number | null
  // direction: "higher_is_better" | "lower_is_better" | "neutral"
): "success" | "error" | "neutral" {
  if (delta == null) {
    return "neutral";
  }

  // Simplified: positive delta is success, negative is error
  // Real implementation should use direction metadata
  return delta > 0 ? "success" : delta < 0 ? "error" : "neutral";
}

/**
 * Format aggregate metric for display.
 */
export function formatAggregateMetric(agg: AggregateResultSummary): string {
  return formatCatalogMetricValue(agg.value_summary, agg.metric_id, agg.aggregation);
}

export {
  formatMetricStatistic,
  getMetricCatalogEntry,
  getMetricDisplayName,
  getMetricStatistics,
  isMetricStatisticAllowed,
} from "./metric-catalog";

/**
 * Truncate text with ellipsis.
 */
export function truncateText(text: string | null, maxLength: number): string {
  if (!text) return "—";
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + "...";
}

/**
 * Format answerability for display.
 */
export function formatAnswerability(answerability: string | null): string {
  if (!answerability) return "—";
  return answerability.replace("_", " ");
}

/**
 * Get answerability badge variant.
 */
export function getAnswerabilityVariant(
  answerability: string | null
): "success" | "warning" | "error" | "info" | "neutral" {
  switch (answerability) {
    case "ANSWERABLE":
      return "success";
    case "UNANSWERABLE":
      return "warning";
    case "AMBIGUOUS":
      return "error";
    default:
      return "neutral";
  }
}
