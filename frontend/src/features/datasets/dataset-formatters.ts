/**
 * Dataset formatters and utilities.
 */
import type { Answerability, DatasetInfo, BenchmarkCase } from "./dataset-types";

/** Format answerability for display */
export function formatAnswerability(
  answerability: Answerability | null | undefined
): string {
  if (!answerability) return "Unknown";

  switch (answerability) {
    case "ANSWERABLE":
      return "Answerable";
    case "UNANSWERABLE":
      return "Unanswerable";
    case "AMBIGUOUS":
      return "Ambiguous";
    case "UNKNOWN":
      return "Unknown";
    default:
      return answerability;
  }
}

/** Get answerability badge variant */
export function getAnswerabilityVariant(
  answerability: Answerability | null | undefined
): "success" | "error" | "warning" | "neutral" {
  if (!answerability) return "neutral";

  switch (answerability) {
    case "ANSWERABLE":
      return "success";
    case "UNANSWERABLE":
      return "error";
    case "AMBIGUOUS":
    case "UNKNOWN":
      return "warning";
    default:
      return "neutral";
  }
}

/** Format difficulty for display */
export function formatDifficulty(difficulty: string | null | undefined): string {
  if (!difficulty) return "—";

  return difficulty.charAt(0).toUpperCase() + difficulty.slice(1);
}

/** Truncate query text for table display */
export function truncateQuery(query: string, maxLength: number = 80): string {
  if (query.length <= maxLength) return query;
  return query.slice(0, maxLength - 3) + "…";
}

/** Format case count with suffix for large numbers */
export function formatCaseCount(count: number | null | undefined): string {
  if (count == null) return "0 cases";
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  if (count < 1000) return `${String(count)} cases`;
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  if (count < 1000000) return `${(count / 1000).toFixed(1)}k cases`;
  return `${(count / 1000000).toFixed(1)}M cases`;
}

/** Get validation status */
export function getValidationStatus(
  valid: number,
  total: number
): "valid" | "invalid" | "unknown" {
  if (total === 0) return "unknown";
  if (valid === total) return "valid";
  return "invalid";
}

/** Get evidence count from case */
export function getEvidenceCount(
  caseData: Pick<BenchmarkCase, "gold_evidence">
): number {
  return caseData.gold_evidence.length;
}

/** Get history message count */
export function getHistoryMessageCount(
  caseData: Pick<BenchmarkCase, "history">
): number {
  return caseData.history.length;
}

/** Format dataset name with version */
export function formatDatasetName(dataset: DatasetInfo): string {
  return `${dataset.name} v${dataset.version}`;
}

/** Format relative time */
export function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString();
}
