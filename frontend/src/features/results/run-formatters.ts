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

/**
 * Format run status for display.
 */
export function formatRunStatus(status: RunStatus): string {
  switch (status) {
    case "queued":
      return "Queued";
    case "running":
      return "Running";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    default:
      return "Unknown";
  }
}

/**
 * Get status badge variant for run status.
 */
export function getRunStatusVariant(
  status: RunStatus
): "success" | "warning" | "error" | "info" | "neutral" {
  switch (status) {
    case "completed":
      return "success";
    case "running":
      return "info";
    case "failed":
      return "error";
    case "cancelled":
      return "neutral";
    default:
      return "neutral";
  }
}

/**
 * Format case status for display.
 */
export function formatCaseStatus(status: CaseStatus): string {
  switch (status) {
    case "queued":
      return "Queued";
    case "running":
      return "Running";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    default:
      return "Unknown";
  }
}

/**
 * Format attempt status for display.
 */
export function formatAttemptStatus(status: AttemptStatus): string {
  switch (status) {
    case "running":
      return "Running";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    case "timeout":
      return "Timeout";
    default:
      return "Unknown";
  }
}

/**
 * Format metric status for display.
 */
export function formatMetricStatus(status: MetricStatus): string {
  switch (status) {
    case "computed":
      return "Computed";
    case "unavailable_missing_input":
      return "Unavailable";
    case "not_applicable":
      return "N/A";
    case "failed":
      return "Failed";
    case "skipped":
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
export function formatMetricValue(value: unknown, metricId?: string): string {
  if (value === null || value === undefined) return "—";

  if (typeof value === "number") {
    // Percentages
    if (
      metricId?.includes("recall") ||
      metricId?.includes("precision") ||
      metricId?.includes("rate")
    ) {
      return `${(value * 100).toFixed(1)}%`;
    }

    // Latency
    if (metricId?.includes("latency")) {
      return `${Math.round(value).toFixed(0)}ms`;
    }

    // Tokens
    if (metricId?.includes("token")) {
      return value.toLocaleString();
    }

    // Cost
    if (metricId?.includes("cost")) {
      return `$${value.toFixed(2)}`;
    }

    // Default decimal formatting
    if (value >= 0 && value <= 1) {
      return `${(value * 100).toFixed(1)}%`;
    }

    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  // eslint-disable-next-line @typescript-eslint/no-base-to-string
  return String(value);
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
  return formatMetricValue(agg.value_summary, agg.metric_id);
}

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
