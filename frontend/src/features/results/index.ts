/**
 * Results/EvaluationRun feature exports.
 */

// Types
export type {
  RunStatus,
  CaseStatus,
  AttemptStatus,
  MetricStatus,
  RunSummary,
  RunDetail,
  RunProgress,
  CaseExecutionSummary,
  CaseExecutionDetail,
  AttemptSummary,
  AttemptDetail,
  TargetObservationSummary,
  TargetObservationDetail,
  MetricResultSummary,
  MetricResultDetail,
  AggregateResultSummary,
  AggregateResultDetail,
  RunReport,
  ComparisonResult,
  ExportRequest,
  ExportResult,
  ErrorDetail,
} from "./run-types";

// Service
export { RunService } from "./run-service";

// Hooks
export {
  runKeys,
  useRunList,
  useRun,
  useRunProgress,
  useCancelRun,
  useRunCases,
  useRunCase,
  useCaseAttempts,
  useObservation,
  useCaseMetrics,
  useRunAggregates,
  useRunReport,
  useRunComparison,
  useExportRun,
} from "./use-runs";

// Formatters
export {
  formatRunStatus,
  getRunStatusVariant,
  formatCaseStatus,
  formatAttemptStatus,
  formatMetricStatus,
  formatProgress,
  formatElapsedTime,
  formatRelativeTime,
  formatMetricValue,
  formatMetricDelta,
  getDeltaVariant,
  formatAggregateMetric,
  truncateText,
  formatAnswerability,
  getAnswerabilityVariant,
} from "./run-formatters";

// Pages
export { ResultsPage } from "./pages/results-page";
export { RunDetailPage } from "./pages/run-detail-page";
export { RunCaseDetailPage } from "./pages/run-case-detail-page";
export { RunComparePage } from "./pages/run-compare-page";
