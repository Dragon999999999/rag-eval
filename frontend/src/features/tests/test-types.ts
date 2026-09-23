/** Frontend contracts for persisted tests, metric configuration, and runs. */

export type MetricRequirement = string;
export type MetricScope = "CASE" | "RUN" | "ATTEMPT" | (string & {});

/** A globally registered metric used by legacy builder consumers. */
export interface MetricDefinition {
  metric_id: string;
  version: string;
  display_name?: string;
  description: string;
  scope: MetricScope;
  requirements: MetricRequirement[] | Array<Record<string, unknown>>;
  category?: string;
  config_schema?: Record<string, unknown>;
}

/** A metric as evaluated for one persisted test. */
export interface TestMetricInfo {
  metric_id: string;
  version: string;
  scope: string;
  description: string;
  requirements: Array<string | Record<string, unknown>>;
  applicable: boolean;
  selected: boolean;
  unavailable_reason: string | null;
  parameters: Record<string, unknown>;
}

export interface TestMetricsInfo {
  test_definition_id: string;
  mode: "EXPLICIT" | "ALL_AVAILABLE" | (string & {});
  metrics: TestMetricInfo[];
  selected_metric_ids: string[];
  applicable_metric_ids: string[];
  judge_config: Record<string, unknown>;
  retrieval_config: Record<string, unknown>;
  warnings: string[];
}

export interface MetricImportResult {
  applied: boolean;
  mode: string;
  selected_metrics: string[];
  ignored_metrics: string[];
  unavailable_metrics: string[];
  detected_target_id: string | null;
  detected_benchmark_id: string | null;
  target_conflict: boolean;
  benchmark_conflict: boolean;
  warnings: string[];
}

export interface ExecutionConfig {
  [key: string]: unknown;
  concurrency?: number;
  timeout_per_request?: number;
  retries?: number;
  failure_policy?: string;
  store_raw_responses?: boolean;
  store_traces?: boolean;
  store_usage?: boolean;
}

/** Complete editable test returned by the test API. */
export interface TestDefinitionInfo {
  test_definition_id: string;
  name: string;
  description: string | null;
  configuration_status: string;
  target_id: string | null;
  benchmark_id: string | null;
  metric_selection_mode: string;
  judge_config: Record<string, unknown>;
  retrieval_config: Record<string, unknown>;
  execution_config: ExecutionConfig;
  seed: number | null;
  tags: string[];
  metadata: Record<string, unknown>;
  definition_hash: string | null;
  created_at: string;
  updated_at: string;
  /** Kept for old builder callers; the new API stores selections on the test. */
  metric_config_id?: string;
}

export type TestDefinition = TestDefinitionInfo;

/** Name-only creation is intentional; configuration is incremental. */
export interface TestDefinitionCreate {
  name: string;
  description?: string | null;
  target_id?: string | null;
  benchmark_id?: string | null;
  metric_config_id?: string;
  execution_config?: Record<string, unknown>;
  seed?: number | null;
  tags?: string[];
  metadata?: Record<string, unknown>;
}

export interface TestDefinitionUpdate {
  name?: string;
  description?: string | null;
  target_id?: string | null;
  benchmark_id?: string | null;
  execution_config?: Record<string, unknown> | null;
  seed?: number | null;
  tags?: string[] | null;
  metadata?: Record<string, unknown> | null;
}

export type TestSummary = Pick<
  TestDefinitionInfo,
  | "test_definition_id"
  | "name"
  | "configuration_status"
  | "target_id"
  | "benchmark_id"
  | "metric_selection_mode"
  | "created_at"
  | "updated_at"
>;

export interface ValidationResult {
  valid: boolean;
  configuration_status: string;
  target_valid: boolean;
  benchmark_valid: boolean;
  metrics_valid: boolean;
  resolved_metric_ids: string[];
  errors: string[];
  warnings: string[];
}

export interface TestDefinitionPlan {
  test_definition_id: string;
  name: string;
  description?: string | null;
  target: Record<string, unknown>;
  benchmark: Record<string, unknown>;
  metric_config: Record<string, unknown>;
  execution_config: Record<string, unknown>;
  seed?: number | null;
  config_hash: string;
  tags: string[];
  experiment_config: Record<string, unknown>;
  estimated_cases?: number;
  estimated_requests?: number;
}

export type CompatibilitySeverity = "warning" | "error";
export interface CompatibilityIssue {
  severity: CompatibilitySeverity;
  code?: string;
  path?: string;
  metric_id?: string;
  message: string;
}

/** Backend lifecycle values are uppercase; lowercase values remain readable for older cached data. */
export type RunStatus =
  | "PENDING"
  | "QUEUED"
  | "RUNNING"
  | "PAUSING"
  | "PAUSED"
  | "INTERRUPTED"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED"
  | "pending"
  | "queued"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled"
  | (string & {});

export interface EvaluationRunSummary {
  run_id: string;
  name: string;
  status: RunStatus;
  status_reason?: string | null;
  config_hash: string;
  target_id: string | null;
  benchmark_id?: string | null;
  test_definition_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  paused_at?: string | null;
  interrupted_at?: string | null;
  created_at: string;
  updated_at?: string;
  total_cases?: number | null;
  complete_cases?: number | null;
  failed_cases?: number | null;
  pending_cases?: number | null;
  running_cases?: number | null;
  progress?: {
    total_cases: number;
    complete_cases: number;
    failed_cases: number;
    pending_cases: number;
    percent: number;
  };
}

export interface RunStatusResponse {
  run_id: string;
  status: RunStatus;
  status_reason: string | null;
  total_cases: number;
  complete_cases: number;
  failed_cases: number;
  pending_cases: number;
  running_cases: number;
  progress_percent: number;
  started_at: string | null;
  finished_at: string | null;
  paused_at?: string | null;
  interrupted_at?: string | null;
  elapsed_seconds: number | null;
}

export interface CreateRunRequest {
  test_definition_id?: string;
  name?: string;
  seed?: number | null;
  tags?: string[];
  metadata?: Record<string, unknown>;
}

/** Legacy form-only types retained while the old builder is being retired. */
export interface MetricConfig {
  metric_config_id?: string;
  name: string;
  mode: "all_available" | "explicit";
  selected_metrics: string[];
  metric_parameters: Record<string, unknown>;
  judge_config: Record<string, unknown>;
  retrieval_config: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}
export type CaseFilter = Record<string, unknown> & {
  tags?: string[];
  difficulty?: string;
  answerability?: string;
};
export type CaseScope =
  | { mode: "all" }
  | { mode: "filtered"; filters: CaseFilter }
  | { mode: "sample"; sample_size: number; seed?: number };
