/**
 * Formatting utilities for test/evaluation display.
 */
import type {
  MetricDefinition,
  MetricScope,
  TestDefinitionInfo,
  EvaluationRunSummary,
  RunStatus,
  CompatibilityIssue,
} from "./test-types";

/**
 * Format metric scope for display.
 */
export function formatMetricScope(scope: MetricScope): string {
  switch (scope) {
    case "CASE":
      return "Per Case";
    case "RUN":
      return "Per Run";
    case "ATTEMPT":
      return "Per Attempt";
    default:
      return scope;
  }
}

/**
 * Format metric ID for display (extract readable name).
 */
export function formatMetricName(metric: MetricDefinition): string {
  return metric.display_name || metric.metric_id.split(".").pop() || metric.metric_id;
}

/**
 * Format metric ID with category prefix.
 */
export function formatMetricFullName(metric: MetricDefinition): string {
  const category = metric.category ? `${metric.category} · ` : "";
  return `${category}${formatMetricName(metric)}`;
}

/**
 * Format run status for display.
 */
export function formatRunStatus(status: RunStatus): string {
  return status
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./, (value) => value.toUpperCase());
}

/**
 * Get status badge variant for run status.
 */
export function getRunStatusVariant(
  status: RunStatus
): "default" | "success" | "error" | "info" {
  switch (status.toLowerCase()) {
    case "completed":
      return "success";
    case "running":
    case "pending":
    case "queued":
    case "pausing":
      return "info";
    case "failed":
      return "error";
    case "cancelled":
      return "default";
    default:
      return "default";
  }
}

/**
 * Format test definition name with fallback.
 */
export function formatTestName(test: TestDefinitionInfo | null | undefined): string {
  if (!test) return "Unnamed Test";
  return test.name || "Unnamed Test";
}

/**
 * Format run name with fallback.
 */
export function formatRunName(run: EvaluationRunSummary | null | undefined): string {
  if (!run) return "Unnamed Run";
  return run.name || `Run ${new Date(run.created_at).toLocaleDateString()}`;
}

/**
 * Format progress percentage with status indicator.
 */
export function formatProgress(progress: EvaluationRunSummary["progress"]): string {
  if (!progress) return "No progress data";

  const { complete_cases, total_cases, percent } = progress;
  return `${String(complete_cases)}/${String(total_cases)} (${String(percent)}%)`;
}

/**
 * Format compatibility issue severity.
 */
export function formatCompatibilitySeverity(
  severity: CompatibilityIssue["severity"]
): string {
  return severity === "error" ? "Error" : "Warning";
}

/**
 * Get badge variant for compatibility severity.
 */
export function getCompatibilitySeverityVariant(
  severity: CompatibilityIssue["severity"]
): "destructive" | "warning" | "outline" {
  switch (severity) {
    case "error":
      return "destructive";
    case "warning":
      return "warning";
    default:
      return "outline";
  }
}

/**
 * Format requirements list for display.
 */
export function formatRequirements(
  requirements: Array<string | Record<string, unknown>>
): string {
  if (requirements.length === 0) return "No requirements";

  return requirements
    .map((req) => {
      const candidate = typeof req === "string" ? req : (req.name ?? req.requirement);
      const requirement = typeof candidate === "string" ? candidate : "requirement";
      // Convert REQUIREMENT_NAME to readable format
      return requirement
        .split("_")
        .map((word) => word.charAt(0) + word.slice(1).toLowerCase())
        .join(" ");
    })
    .join(", ");
}

/**
 * Format execution config for display.
 */
export function formatExecutionConfig(config: Record<string, unknown>): string {
  const parts: string[] = [];

  if (typeof config.concurrency === "number") {
    parts.push(`${String(config.concurrency)} concurrent`);
  }

  if (typeof config.timeout_per_request === "number") {
    parts.push(`${String(config.timeout_per_request)}s timeout`);
  }

  if (typeof config.retries === "number") {
    parts.push(`${String(config.retries)} retries`);
  }

  if (config.failure_policy) {
    const policy =
      typeof config.failure_policy === "string" ? config.failure_policy : "unknown";
    parts.push(`on failure: ${policy}`);
  }

  return parts.join(" · ") || "Default";
}

/**
 * Format relative time for display.
 */
export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${String(diffMins)}m ago`;
  if (diffHours < 24) return `${String(diffHours)}h ago`;
  if (diffDays < 7) return `${String(diffDays)}d ago`;

  return date.toLocaleDateString();
}

/**
 * Format case count with K suffix for large numbers.
 */
export function formatCaseCount(count: number): string {
  if (count >= 1000000) {
    return `${(count / 1000000).toFixed(1)}M`;
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}K`;
  }
  return count.toString();
}

/**
 * Truncate text with ellipsis.
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + "...";
}
