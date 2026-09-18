/**
 * EvaluationRun domain types.
 *
 * Based on canonical backend Run, CaseExecution, Attempt, TargetObservation, and MetricResult models.
 */

/** Run status - canonical backend values */
export type RunStatus = "queued" | "running" | "completed" | "failed" | "cancelled" | "unknown";

/** Case execution status */
export type CaseStatus = "queued" | "running" | "completed" | "failed" | "cancelled" | "unknown";

/** Attempt status */
export type AttemptStatus = "running" | "completed" | "failed" | "cancelled" | "timeout" | "unknown";

/** Metric result status */
export type MetricStatus = "computed" | "unavailable_missing_input" | "not_applicable" | "failed" | "skipped";

/** Run summary for listing */
export interface RunSummary {
  run_id: string;
  name: string;
  status: RunStatus;
  config_hash: string;
  target_id: string | null;
  test_definition_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  // Computed progress fields
  total_cases?: number;
  complete_cases?: number;
  failed_cases?: number;
  pending_cases?: number;
  progress_percent?: number;
}

/** Detailed run information */
export interface RunDetail {
  run_id: string;
  name: string;
  status: RunStatus;
  config_hash: string;
  target_id: string | null;
  test_definition_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  seed: number | null;
  rag_eval_version: string | null;
  tags: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  // Computed fields
  total_cases?: number;
  complete_cases?: number;
  failed_cases?: number;
  pending_cases?: number;
}

/** Run progress information */
export interface RunProgress {
  run_id: string;
  status: RunStatus;
  total_cases: number;
  complete_cases: number;
  failed_cases: number;
  pending_cases: number;
  running_cases: number;
  progress_percent: number;
  started_at: string | null;
  finished_at: string | null;
  elapsed_seconds: number | null;
}

/** Case execution summary for listing */
export interface CaseExecutionSummary {
  case_execution_id: string;
  case_id: string;
  status: CaseStatus;
  started_at: string | null;
  finished_at: string | null;
  attempt_count: number | null;
}

/** Detailed case execution information */
export interface CaseExecutionDetail {
  case_execution_id: string;
  run_id: string;
  case_id: string;
  status: CaseStatus;
  started_at: string | null;
  finished_at: string | null;
  metadata: Record<string, unknown>;
  // Related data
  query: string | null;
  reference_answer: string | null;
  answerability: string | null;
  tags: string[];
}

/** Attempt summary for listing */
export interface AttemptSummary {
  attempt_id: string;
  attempt_number: number;
  status: AttemptStatus;
  request_id: string;
  started_at: string | null;
  finished_at: string | null;
  retryable: boolean | null;
  error_summary: string | null;
}

/** Detailed attempt information */
export interface AttemptDetail {
  attempt_id: string;
  case_execution_id: string;
  attempt_number: number;
  request_id: string;
  idempotency_key: string | null;
  canonical_request_hash: string | null;
  status: AttemptStatus;
  started_at: string | null;
  finished_at: string | null;
  metadata: Record<string, unknown>;
}

/** Target observation summary */
export interface TargetObservationSummary {
  observation_id: string;
  request_id: string;
  has_answer: boolean;
  answer_length: number | null;
  retrieval_stage_count: number;
  citation_count: number;
  has_trace: boolean;
  has_usage: boolean;
  error_count: number;
  created_at: string;
}

/** Detailed target observation */
export interface TargetObservationDetail {
  observation_id: string;
  request_id: string;
  case_execution_id: string;
  attempt_id: string;
  answer: Record<string, unknown> | null;
  retrieval: Record<string, unknown> | null;
  citations: Array<Record<string, unknown>>;
  confidence: Array<Record<string, unknown>>;
  trace: Record<string, unknown> | null;
  usage: Record<string, unknown> | null;
  errors: Array<Record<string, unknown>>;
  warnings: Array<Record<string, unknown>>;
  normalization_version: string;
  created_at: string;
}

/** Metric result summary */
export interface MetricResultSummary {
  metric_id: string;
  metric_version: string;
  status: MetricStatus;
  has_value: boolean;
  value_summary: string | null;
}

/** Detailed metric result */
export interface MetricResultDetail {
  metric_result_id: string;
  run_id: string;
  case_execution_id: string | null;
  case_id: string | null;
  metric_id: string;
  metric_version: string;
  value: unknown | null;
  status: MetricStatus;
  reason: string | null;
  details: Record<string, unknown>;
  payload: Record<string, unknown>;
  created_at: string;
}

/** Aggregate metric result summary */
export interface AggregateResultSummary {
  metric_id: string;
  metric_version: string;
  aggregation: string;
  status: MetricStatus;
  value_summary: string | null;
}

/** Detailed aggregate metric result */
export interface AggregateResultDetail {
  aggregate_metric_result_id: string;
  run_id: string;
  metric_id: string;
  metric_version: string;
  aggregation: string;
  value: unknown | null;
  status: MetricStatus;
  reason: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

/** Run report */
export interface RunReport {
  run_id: string;
  run_name: string;
  status: RunStatus;
  target_id: string | null;
  config_hash: string;
  total_cases: number;
  complete_cases: number;
  failed_cases: number;
  pending_cases: number;
  answer_metrics: Record<string, unknown>;
  retrieval_metrics: Record<string, unknown>;
  citation_metrics: Record<string, unknown>;
  performance_metrics: Record<string, unknown>;
  usage_metrics: Record<string, unknown>;
  cost_metrics: Record<string, unknown>;
  reliability_metrics: Record<string, unknown>;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
}

/** Run comparison result */
export interface ComparisonResult {
  run_a_id: string;
  run_b_id: string;
  compatibility_warnings: string[];
  metric_comparisons: Array<{
    metric_id: string;
    metric_version: string;
    aggregation: string;
    run_a_value: unknown;
    run_b_value: unknown;
    absolute_delta: number | null;
    relative_delta_percent: number | null;
    direction: "higher_is_better" | "lower_is_better" | "neutral";
    status: "improved" | "regressed" | "unchanged" | "incomparable";
  }>;
  summary: Record<string, unknown>;
  compared_at: string;
}

/** Export request */
export interface ExportRequest {
  formats: string[];
  include_raw_artifacts: boolean;
}

/** Export result */
export interface ExportResult {
  run_id: string;
  export_id: string;
  status: string;
  files: Array<{
    filename: string;
    format: string;
    size_bytes: number;
    download_url: string;
  }>;
  download_url: string | null;
  created_at: string;
}

/** Error detail */
export interface ErrorDetail {
  error_id: string;
  category: string;
  code: string;
  message: string;
  stage: string | null;
  retryable: boolean;
  retry_after_ms: number | null;
  http_status: number | null;
  created_at: string;
}
