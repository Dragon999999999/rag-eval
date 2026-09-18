/**
 * Run service API client.
 *
 * Centralized service for EvaluationRun operations.
 * Uses mock implementation - replace with real HTTP calls when backend is available.
 */
import type {
  RunSummary,
  RunDetail,
  RunProgress,
  CaseExecutionSummary,
  CaseExecutionDetail,
  AttemptSummary,
  AttemptDetail,
  TargetObservationDetail,
  MetricResultSummary,
  MetricResultDetail,
  AggregateResultSummary,
  AggregateResultDetail,
  RunReport,
  ComparisonResult,
  ExportRequest,
  ExportResult,
} from "./run-types";

const MOCK_DELAY_MS = 400;

/** Error with code and status properties */
interface ServiceError extends Error {
  code?: string;
  status?: number;
}

/** Transform AttemptDetail to AttemptSummary */
function toAttemptSummary(detail: AttemptDetail): AttemptSummary {
  return {
    attempt_id: detail.attempt_id,
    attempt_number: detail.attempt_number,
    status: detail.status,
    request_id: detail.request_id,
    started_at: detail.started_at,
    finished_at: detail.finished_at,
    retryable: detail.metadata.retryable as boolean | null,
    error_summary: detail.metadata.error as string | null,
  };
}

/** Transform MetricResultDetail to MetricResultSummary */
function toMetricResultSummary(detail: MetricResultDetail): MetricResultSummary {
  return {
    metric_id: detail.metric_id,
    metric_version: detail.metric_version,
    status: detail.status,
    has_value: detail.value != null,
    value_summary: detail.value != null ? JSON.stringify(detail.value) : null,
  };
}

/** Transform AggregateResultDetail to AggregateResultSummary */
function toAggregateResultSummary(
  detail: AggregateResultDetail
): AggregateResultSummary {
  return {
    metric_id: detail.metric_id,
    metric_version: detail.metric_version,
    aggregation: detail.aggregation,
    status: detail.status,
    value_summary: detail.value != null ? JSON.stringify(detail.value) : null,
  };
}

/** Transform CaseExecutionDetail to CaseExecutionSummary */
function toCaseExecutionSummary(detail: CaseExecutionDetail): CaseExecutionSummary {
  return {
    case_execution_id: detail.case_execution_id,
    case_id: detail.case_id,
    status: detail.status,
    started_at: detail.started_at,
    finished_at: detail.finished_at,
    attempt_count: null, // Would be computed from attempts in real implementation
  };
}

/** In-memory mock run store */
const mockRuns = new Map<string, RunDetail>();
const mockCaseExecutions = new Map<string, CaseExecutionDetail>();
const mockAttempts = new Map<string, AttemptDetail>();
const mockObservations = new Map<string, TargetObservationDetail>();
const mockMetricResults = new Map<string, MetricResultDetail>();
const mockAggregateResults = new Map<string, AggregateResultDetail>();

/** Initialize with mock data */
function initializeMockData() {
  if (mockRuns.size > 0) return;

  // Sample completed run
  const run1: RunDetail = {
    run_id: "run-completed-001",
    name: "Grounding Regression - Run #1",
    status: "completed",
    config_hash: "sha256:abc123...",
    target_id: "target-http-001",
    test_definition_id: "test-001",
    started_at: new Date(Date.now() - 3600000).toISOString(),
    finished_at: new Date(Date.now() - 1800000).toISOString(),
    seed: 42,
    rag_eval_version: "0.1.0",
    tags: ["regression", "grounding"],
    metadata: {},
    created_at: new Date(Date.now() - 3600000).toISOString(),
    updated_at: new Date(Date.now() - 1800000).toISOString(),
    total_cases: 250,
    complete_cases: 248,
    failed_cases: 2,
    pending_cases: 0,
  };

  mockRuns.set(run1.run_id, run1);

  // Sample running run
  const run2: RunDetail = {
    run_id: "run-running-002",
    name: "Answer Quality - Run #5",
    status: "running",
    config_hash: "sha256:def456...",
    target_id: "target-http-001",
    test_definition_id: "test-002",
    started_at: new Date(Date.now() - 900000).toISOString(),
    finished_at: null,
    seed: 123,
    rag_eval_version: "0.1.0",
    tags: ["answer-quality"],
    metadata: {},
    created_at: new Date(Date.now() - 900000).toISOString(),
    updated_at: new Date(Date.now() - 600000).toISOString(),
    total_cases: 250,
    complete_cases: 142,
    failed_cases: 1,
    pending_cases: 107,
  };

  mockRuns.set(run2.run_id, run2);

  // Sample failed run
  const run3: RunDetail = {
    run_id: "run-failed-003",
    name: "Full Benchmark - Failed Run",
    status: "failed",
    config_hash: "sha256:ghi789...",
    target_id: "target-python-001",
    test_definition_id: "test-003",
    started_at: new Date(Date.now() - 7200000).toISOString(),
    finished_at: new Date(Date.now() - 6900000).toISOString(),
    seed: null,
    rag_eval_version: "0.1.0",
    tags: ["benchmark"],
    metadata: { failure_reason: "Target unavailable" },
    created_at: new Date(Date.now() - 7200000).toISOString(),
    updated_at: new Date(Date.now() - 6900000).toISOString(),
    total_cases: 500,
    complete_cases: 45,
    failed_cases: 45,
    pending_cases: 455,
  };

  mockRuns.set(run3.run_id, run3);

  // Sample case executions
  const case1: CaseExecutionDetail = {
    case_execution_id: "case-exec-001",
    run_id: "run-completed-001",
    case_id: "case-001",
    status: "completed",
    started_at: new Date(Date.now() - 3500000).toISOString(),
    finished_at: new Date(Date.now() - 3400000).toISOString(),
    metadata: {},
    query: "What is CV-QKD?",
    reference_answer: "CV-QKD stands for Continuous Variable Quantum Key Distribution.",
    answerability: "ANSWERABLE",
    tags: ["qkd", "physics"],
  };

  mockCaseExecutions.set(case1.case_execution_id, case1);

  // Sample aggregate metrics
  const agg1: AggregateResultDetail = {
    aggregate_metric_result_id: "agg-001",
    run_id: "run-completed-001",
    metric_id: "retrieval.recall_at_k",
    metric_version: "1.0",
    aggregation: "mean",
    value: 0.912,
    status: "computed",
    reason: null,
    details: { k: 5 },
    created_at: new Date(Date.now() - 1800000).toISOString(),
  };

  mockAggregateResults.set(agg1.aggregate_metric_result_id, agg1);

  const agg2: AggregateResultDetail = {
    aggregate_metric_result_id: "agg-002",
    run_id: "run-completed-001",
    metric_id: "grounding.citation_recall",
    metric_version: "1.0",
    aggregation: "mean",
    value: 0.884,
    status: "computed",
    reason: null,
    details: {},
    created_at: new Date(Date.now() - 1800000).toISOString(),
  };

  mockAggregateResults.set(agg2.aggregate_metric_result_id, agg2);
}

export const RunService = {
  /** List runs with optional filters */
  async listRuns(filters?: {
    status?: string;
    test_definition_id?: string;
    target_id?: string;
    benchmark_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<RunSummary[]> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    let runs = Array.from(mockRuns.values());

    // Apply filters
    if (filters?.status) {
      runs = runs.filter((r) => r.status === filters.status);
    }

    if (filters?.test_definition_id) {
      runs = runs.filter((r) => r.test_definition_id === filters.test_definition_id);
    }

    if (filters?.target_id) {
      runs = runs.filter((r) => r.target_id === filters.target_id);
    }

    // Sort by created_at descending
    runs.sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );

    // Apply pagination
    const limit = filters?.limit ?? 100;
    const offset = filters?.offset ?? 0;
    return runs.slice(offset, offset + limit);
  },

  /** Get detailed run information */
  async getRun(runId: string): Promise<RunDetail> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const run = mockRuns.get(runId);
    if (!run) {
      const error = new Error(`Run not found: ${runId}`);
      (error as ServiceError).code = "RUN_NOT_FOUND";
      (error as ServiceError).status = 404;
      throw error;
    }

    return run;
  },

  /** Get run progress */
  async getRunProgress(runId: string): Promise<RunProgress> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const run = mockRuns.get(runId);
    if (!run) {
      const error = new Error(`Run not found: ${runId}`);
      (error as ServiceError).code = "RUN_NOT_FOUND";
      (error as ServiceError).status = 404;
      throw error;
    }

    const now = Date.now();
    const started = run.started_at ? new Date(run.started_at).getTime() : now;
    const finished = run.finished_at ? new Date(run.finished_at).getTime() : now;
    const elapsed = run.finished_at
      ? (finished - started) / 1000
      : (now - started) / 1000;

    return {
      run_id: run.run_id,
      status: run.status,
      total_cases: run.total_cases ?? 0,
      complete_cases: run.complete_cases ?? 0,
      failed_cases: run.failed_cases ?? 0,
      pending_cases: run.pending_cases ?? 0,
      running_cases: Math.max(
        0,
        (run.total_cases ?? 0) - (run.complete_cases ?? 0) - (run.failed_cases ?? 0)
      ),
      progress_percent: run.total_cases
        ? Math.round(((run.complete_cases ?? 0) / run.total_cases) * 100)
        : 0,
      started_at: run.started_at,
      finished_at: run.finished_at,
      elapsed_seconds: Math.round(elapsed),
    };
  },

  /** Cancel a running evaluation */
  async cancelRun(runId: string): Promise<void> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS + 300));

    const run = mockRuns.get(runId);
    if (!run) {
      const error = new Error(`Run not found: ${runId}`);
      (error as ServiceError).code = "RUN_NOT_FOUND";
      (error as ServiceError).status = 404;
      throw error;
    }

    if (run.status !== "running" && run.status !== "queued") {
      const error = new Error(`Run cannot be cancelled: ${run.status}`);
      (error as ServiceError).code = "RUN_CANNOT_CANCEL";
      (error as ServiceError).status = 400;
      throw error;
    }

    // Update run status
    run.status = "cancelled";
    run.finished_at = new Date().toISOString();
    mockRuns.set(runId, run);
  },

  /** Get cases for a run with pagination */
  async getRunCases(
    runId: string,
    filters?: {
      limit?: number;
      offset?: number;
      status?: string;
      search?: string;
      tags?: string[];
      answerability?: string;
    }
  ): Promise<{ cases: CaseExecutionSummary[]; total: number }> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    // Get all case executions for this run
    let cases = Array.from(mockCaseExecutions.values()).filter(
      (c) => c.run_id === runId
    );

    // Apply filters
    if (filters?.status) {
      cases = cases.filter((c) => c.status === filters.status);
    }

    if (filters?.search) {
      const searchLower = filters.search.toLowerCase();
      cases = cases.filter((c) => c.query?.toLowerCase().includes(searchLower));
    }

    if (filters?.answerability) {
      cases = cases.filter((c) => c.answerability === filters.answerability);
    }

    const total = cases.length;

    // Apply pagination
    const limit = filters?.limit ?? 50;
    const offset = filters?.offset ?? 0;
    const paginated = cases.slice(offset, offset + limit);

    return { cases: paginated.map(toCaseExecutionSummary), total };
  },

  /** Get detailed case execution information */
  async getRunCase(runId: string, caseId: string): Promise<CaseExecutionDetail> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const caseExec = Array.from(mockCaseExecutions.values()).find(
      (c) => c.run_id === runId && c.case_id === caseId
    );

    if (!caseExec) {
      const error = new Error(`Case not found: ${caseId} in run ${runId}`);
      (error as ServiceError).code = "CASE_NOT_FOUND";
      (error as ServiceError).status = 404;
      throw error;
    }

    return caseExec;
  },

  /** Get attempts for a case execution */
  async getCaseAttempts(runId: string, caseId: string): Promise<AttemptSummary[]> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const caseExec = Array.from(mockCaseExecutions.values()).find(
      (c) => c.run_id === runId && c.case_id === caseId
    );

    if (!caseExec) {
      return [];
    }

    const attempts = Array.from(mockAttempts.values())
      .filter((a) => a.case_execution_id === caseExec.case_execution_id)
      .sort((a, b) => a.attempt_number - b.attempt_number);

    return attempts.map(toAttemptSummary);
  },

  /** Get detailed attempt information */
  async getAttempt(
    _runId: string,
    _caseId: string,
    attemptId: string
  ): Promise<AttemptDetail> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const attempt = mockAttempts.get(attemptId);
    if (!attempt) {
      const error = new Error(`Attempt not found: ${attemptId}`);
      (error as ServiceError).code = "ATTEMPT_NOT_FOUND";
      (error as ServiceError).status = 404;
      throw error;
    }

    return attempt;
  },

  /** Get target observation for a case/attempt */
  async getObservation(
    runId: string,
    caseId: string,
    _attemptId?: string
  ): Promise<TargetObservationDetail | null> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const caseExec = Array.from(mockCaseExecutions.values()).find(
      (c) => c.run_id === runId && c.case_id === caseId
    );

    if (!caseExec) {
      return null;
    }

    const observation = Array.from(mockObservations.values()).find(
      (o) => o.case_execution_id === caseExec.case_execution_id
    );

    return observation ?? null;
  },

  /** Get metric results for a case */
  async getCaseMetrics(runId: string, caseId: string): Promise<MetricResultSummary[]> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const caseExec = Array.from(mockCaseExecutions.values()).find(
      (c) => c.run_id === runId && c.case_id === caseId
    );

    if (!caseExec) {
      return [];
    }

    const metrics = Array.from(mockMetricResults.values()).filter(
      (m) => m.case_execution_id === caseExec.case_execution_id
    );

    return metrics.map(toMetricResultSummary);
  },

  /** Get aggregate metrics for a run */
  async getRunAggregates(runId: string): Promise<AggregateResultSummary[]> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const aggregates = Array.from(mockAggregateResults.values()).filter(
      (a) => a.run_id === runId
    );

    return aggregates.map(toAggregateResultSummary);
  },

  /** Get run report */
  async getRunReport(runId: string): Promise<RunReport> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS + 200));

    const run = mockRuns.get(runId);
    if (!run) {
      const error = new Error(`Run not found: ${runId}`);
      (error as ServiceError).code = "RUN_NOT_FOUND";
      (error as ServiceError).status = 404;
      throw error;
    }

    const started = run.started_at ? new Date(run.started_at).getTime() : Date.now();
    const finished = run.finished_at ? new Date(run.finished_at).getTime() : Date.now();
    const duration = run.finished_at ? (finished - started) / 1000 : null;

    return {
      run_id: run.run_id,
      run_name: run.name,
      status: run.status,
      target_id: run.target_id,
      config_hash: run.config_hash,
      total_cases: run.total_cases ?? 0,
      complete_cases: run.complete_cases ?? 0,
      failed_cases: run.failed_cases ?? 0,
      pending_cases: run.pending_cases ?? 0,
      answer_metrics: { correctness: 0.87, exact_match: 0.72 },
      retrieval_metrics: { recall_at_5: 0.91, mrr: 0.85 },
      citation_metrics: { citation_recall: 0.88, citation_precision: 0.92 },
      performance_metrics: { latency_ms: 820, tokens_per_second: 45 },
      usage_metrics: {
        total_tokens: 125000,
        input_tokens: 95000,
        output_tokens: 30000,
      },
      cost_metrics: { total_cost_usd: 2.45 },
      reliability_metrics: { success_rate: 0.992 },
      started_at: run.started_at,
      finished_at: run.finished_at,
      duration_seconds: duration,
    };
  },

  /** Compare two runs */
  async compareRuns(runAId: string, runBId: string): Promise<ComparisonResult> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS + 400));

    const runA = mockRuns.get(runAId);
    const runB = mockRuns.get(runBId);

    if (!runA || !runB) {
      const error = new Error("One or both runs not found");
      (error as ServiceError).code = "RUN_NOT_FOUND";
      (error as ServiceError).status = 404;
      throw error;
    }

    // Check compatibility
    const compatibilityWarnings: string[] = [];
    if (runA.config_hash !== runB.config_hash) {
      compatibilityWarnings.push("Runs have different configurations");
    }
    if (runA.target_id !== runB.target_id) {
      compatibilityWarnings.push("Runs use different targets");
    }

    return {
      run_a_id: runAId,
      run_b_id: runBId,
      compatibility_warnings: compatibilityWarnings,
      metric_comparisons: [
        {
          metric_id: "retrieval.recall_at_k",
          metric_version: "1.0",
          aggregation: "mean",
          run_a_value: 0.912,
          run_b_value: 0.863,
          absolute_delta: 0.049,
          relative_delta_percent: 5.68,
          direction: "higher_is_better",
          status: "improved",
        },
        {
          metric_id: "grounding.citation_recall",
          metric_version: "1.0",
          aggregation: "mean",
          run_a_value: 0.884,
          run_b_value: 0.856,
          absolute_delta: 0.028,
          relative_delta_percent: 3.27,
          direction: "higher_is_better",
          status: "improved",
        },
        {
          metric_id: "performance.total_latency_ms",
          metric_version: "1.0",
          aggregation: "mean",
          run_a_value: 820,
          run_b_value: 760,
          absolute_delta: 60,
          relative_delta_percent: -7.89,
          direction: "lower_is_better",
          status: "regressed",
        },
      ],
      summary: {
        total_improved: 2,
        total_regressed: 1,
        total_unchanged: 0,
      },
      compared_at: new Date().toISOString(),
    };
  },

  /** Export run results */
  async exportRun(runId: string, request: ExportRequest): Promise<ExportResult> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS + 1000));

    const run = mockRuns.get(runId);
    if (!run) {
      const error = new Error(`Run not found: ${runId}`);
      (error as ServiceError).code = "RUN_NOT_FOUND";
      (error as ServiceError).status = 404;
      throw error;
    }

    if (run.status !== "completed") {
      const error = new Error("Can only export completed runs");
      (error as ServiceError).code = "RUN_NOT_COMPLETED";
      (error as ServiceError).status = 400;
      throw error;
    }

    const exportId = `export-${String(Date.now())}-${Math.random().toString(36).slice(2, 8)}`;
    const files = request.formats.map((format) => ({
      filename: `${runId}.${format}`,
      format,
      size_bytes: Math.floor(Math.random() * 1000000) + 100000,
      download_url: `/api/v1/exports/${exportId}/${runId}.${format}`,
    }));

    return {
      run_id: runId,
      export_id: exportId,
      status: "completed",
      files,
      download_url: files[0]?.download_url ?? null,
      created_at: new Date().toISOString(),
    };
  },
};
