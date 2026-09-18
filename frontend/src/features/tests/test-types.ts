/**
 * Test/Evaluation domain types.
 *
 * Based on canonical backend TestDefinition, MetricConfig, and EvaluationRun models.
 */

/** Metric requirement enum - canonical backend values */
export type MetricRequirement =
  | "REFERENCE_ANSWER"
  | "GOLD_EVIDENCE"
  | "TARGET_CITATIONS"
  | "TARGET_CONFIDENCE"
  | "TARGET_TRACE"
  | "TARGET_USAGE"
  | "TARGET_RETRIEVAL"
  | "RUN_METADATA"
  | "JUDGE_MODEL";

/** Metric scope */
export type MetricScope = "CASE" | "RUN" | "ATTEMPT";

/** Metric definition from backend registry */
export interface MetricDefinition {
  metric_id: string;
  version: string;
  display_name: string;
  description: string;
  scope: MetricScope;
  requirements: MetricRequirement[];
  category?: string;
  config_schema?: Record<string, unknown>;
}

/** Metric configuration for a test */
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

/** Execution configuration */
export interface ExecutionConfig {
  concurrency?: number;
  timeout_per_request?: number;
  retries?: number;
  failure_policy?: "continue" | "abort";
  store_raw_responses?: boolean;
  store_traces?: boolean;
  store_usage?: boolean;
  [key: string]: unknown;
}

/** Case scope configuration */
export type CaseScope =
  | { mode: "all" }
  | { mode: "filtered"; filters: CaseFilter }
  | { mode: "sample"; sample_size: number; seed?: number };

/** Case filter */
export interface CaseFilter {
  tags?: string[];
  difficulty?: string;
  answerability?: string;
  [key: string]: unknown;
}

/** Test definition - reusable evaluation configuration */
export interface TestDefinition {
  test_definition_id: string;
  name: string;
  description?: string | null;
  target_id: string;
  benchmark_id: string;
  metric_config_id: string;
  execution_config: ExecutionConfig;
  seed?: number | null;
  tags: string[];
  metadata?: Record<string, unknown>;
  definition_hash: string;
  created_at: string;
  updated_at: string;
}

/** Test definition create payload */
export interface TestDefinitionCreate {
  name: string;
  description?: string | null;
  target_id: string;
  benchmark_id: string;
  metric_config_id: string;
  execution_config?: Record<string, unknown>;
  seed?: number | null;
  tags?: string[];
  metadata?: Record<string, unknown>;
}

/** Test definition update payload */
export interface TestDefinitionUpdate {
  name?: string;
  description?: string | null;
  target_id?: string;
  benchmark_id?: string;
  metric_config_id?: string;
  execution_config?: Record<string, unknown> | null;
  seed?: number | null;
  tags?: string[] | null;
  metadata?: Record<string, unknown> | null;
}

/** Test definition info for listing */
export interface TestDefinitionInfo {
  test_definition_id: string;
  name: string;
  description?: string | null;
  target_id: string;
  benchmark_id: string;
  metric_config_id: string;
  execution_config: Record<string, unknown>;
  seed?: number | null;
  tags: string[];
  metadata?: Record<string, unknown>;
  definition_hash: string;
  created_at: string;
  updated_at: string;
}

/** Test definition plan result */
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

/** Compatibility issue severity */
export type CompatibilitySeverity = "warning" | "error";

/** Compatibility issue */
export interface CompatibilityIssue {
  severity: CompatibilitySeverity;
  code?: string;
  path?: string;
  metric_id?: string;
  message: string;
}

/** Validation result */
export interface ValidationResult {
  valid: boolean;
  structural_valid: boolean;
  capabilities_valid?: boolean | null;
  errors: string[];
  warnings: string[];
  issues?: CompatibilityIssue[];
}

/** Evaluation run status */
export type RunStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

/** Evaluation run summary */
export interface EvaluationRunSummary {
  run_id: string;
  name: string;
  status: RunStatus;
  config_hash: string;
  target_id: string | null;
  test_definition_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  progress?: {
    total_cases: number;
    complete_cases: number;
    failed_cases: number;
    pending_cases: number;
    percent: number;
  };
}

/** Create run request */
export interface CreateRunRequest {
  test_definition_id?: string;
  name?: string;
  seed?: number | null;
  tags?: string[];
  metadata?: Record<string, unknown>;
}
