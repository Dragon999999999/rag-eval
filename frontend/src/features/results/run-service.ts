/** HTTP client for persisted test runs and their metric results. */

import { apiRequest } from "@/lib/api/client";
import type {
  AggregateResultDetail,
  AggregateResultSummary,
  AttemptDetail,
  AttemptSummary,
  CaseExecutionDetail,
  CaseExecutionSummary,
  ComparisonResult,
  ExportRequest,
  ExportResult,
  MetricResultDetail,
  MetricResultSummary,
  RunDetail,
  RunProgress,
  RunReport,
  RunSummary,
  TargetObservationDetail,
} from "./run-types";

const testsPath = "/api/v1/tests";

interface TestSummaryResponse {
  test_definition_id: string;
}

interface RunResultsResponse {
  run_id: string;
  metrics: MetricResultDetail[];
  aggregates: AggregateResultDetail[];
}

interface ErrorWithStatus extends Error {
  status?: number;
}

function runPath(runId: string): string {
  return `${testsPath}/runs/${encodeURIComponent(runId)}`;
}

function normalizeStatus(status: string): string {
  return status.toUpperCase();
}

function toRunSummary(run: RunDetail): RunSummary {
  return { ...run, status: normalizeStatus(run.status) };
}

function toAttemptSummary(attempt: AttemptDetail): AttemptSummary {
  return {
    ...attempt,
    status: normalizeStatus(attempt.status),
    retryable: attempt.retryable,
    error_summary: attempt.error_summary,
  };
}

function toMetricResultSummary(detail: MetricResultDetail): MetricResultSummary {
  return {
    metric_id: detail.metric_id,
    metric_version: detail.metric_version,
    status: normalizeStatus(detail.status),
    has_value: detail.value !== null && detail.value !== undefined,
    value_summary:
      detail.value === null || detail.value === undefined
        ? null
        : JSON.stringify(detail.value),
  };
}

function toAggregateResultSummary(
  detail: AggregateResultDetail
): AggregateResultSummary {
  return {
    metric_id: detail.metric_id,
    metric_version: detail.metric_version,
    aggregation: detail.aggregation,
    status: normalizeStatus(detail.status),
    value_summary:
      detail.value === null || detail.value === undefined
        ? null
        : JSON.stringify(detail.value),
  };
}

async function getResults(runId: string): Promise<RunResultsResponse> {
  return apiRequest<RunResultsResponse>(`${runPath(runId)}/results`);
}

async function getCases(runId: string): Promise<CaseExecutionDetail[]> {
  return apiRequest<CaseExecutionDetail[]>(`${runPath(runId)}/cases`);
}

function findCase(
  cases: CaseExecutionDetail[],
  caseId: string
): CaseExecutionDetail | undefined {
  return cases.find(
    (item) => item.case_id === caseId || item.case_execution_id === caseId
  );
}

export const RunService = {
  /** List runs by collecting the runs belonging to each configured test. */
  async listRuns(filters?: {
    status?: string;
    test_definition_id?: string;
    target_id?: string;
    benchmark_id?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<RunSummary[]> {
    const tests = filters?.test_definition_id
      ? [{ test_definition_id: filters.test_definition_id }]
      : await apiRequest<TestSummaryResponse[]>(testsPath);
    const runGroups = await Promise.all(
      tests.map((test) =>
        apiRequest<RunDetail[]>(
          `${testsPath}/${encodeURIComponent(test.test_definition_id)}/runs`
        )
      )
    );
    const normalizedStatus = filters?.status
      ? normalizeStatus(filters.status)
      : undefined;
    const search = filters?.search?.trim().toLowerCase();
    const runs = runGroups
      .flat()
      .map(toRunSummary)
      .filter((run) =>
        normalizedStatus ? normalizeStatus(run.status) === normalizedStatus : true
      )
      .filter((run) =>
        filters?.target_id ? run.target_id === filters.target_id : true
      )
      .filter((run) =>
        filters?.benchmark_id ? run.benchmark_id === filters.benchmark_id : true
      )
      .filter((run) =>
        search ? `${run.name} ${run.run_id}`.toLowerCase().includes(search) : true
      )
      .sort(
        (left, right) =>
          new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
      );
    const offset = filters?.offset ?? 0;
    return runs.slice(offset, offset + (filters?.limit ?? 50));
  },

  async getRun(runId: string): Promise<RunDetail> {
    const run = await apiRequest<RunDetail>(runPath(runId));
    return { ...run, status: normalizeStatus(run.status) };
  },

  async getRunProgress(runId: string): Promise<RunProgress> {
    const progress = await apiRequest<RunProgress>(`${runPath(runId)}/status`);
    return { ...progress, status: normalizeStatus(progress.status) };
  },

  async cancelRun(runId: string): Promise<RunDetail> {
    return apiRequest<RunDetail>(`${runPath(runId)}/cancel`, { method: "POST" });
  },

  async resumeRun(runId: string): Promise<RunDetail> {
    return apiRequest<RunDetail>(`${runPath(runId)}/resume`, { method: "POST" });
  },

  async recoverRun(runId: string): Promise<RunDetail> {
    return apiRequest<RunDetail>(`${runPath(runId)}/recover`, { method: "POST" });
  },

  async retryFailedCases(runId: string): Promise<RunDetail> {
    return apiRequest<RunDetail>(`${runPath(runId)}/retry-failed`, {
      method: "POST",
    });
  },

  async getRunCases(
    runId: string,
    filters?: { status?: string; search?: string }
  ): Promise<{ cases: CaseExecutionSummary[]; total: number }> {
    const cases = await getCases(runId);
    const status = filters?.status ? normalizeStatus(filters.status) : undefined;
    const search = filters?.search?.trim().toLowerCase();
    const filtered = cases
      .filter((item) => (status ? normalizeStatus(item.status) === status : true))
      .filter((item) =>
        search
          ? `${item.case_id} ${item.query ?? ""}`.toLowerCase().includes(search)
          : true
      );
    return {
      cases: filtered.map((item) => ({
        ...item,
        status: normalizeStatus(item.status),
        attempt_count: item.attempt_count ?? null,
      })),
      total: filtered.length,
    };
  },

  async getRunCase(runId: string, caseId: string): Promise<CaseExecutionDetail> {
    const item = findCase(await getCases(runId), caseId);
    if (!item) {
      const error: ErrorWithStatus = new Error(`Case not found: ${caseId}`);
      error.status = 404;
      throw error;
    }
    return { ...item, status: normalizeStatus(item.status) };
  },

  async getCaseAttempts(runId: string, caseId: string): Promise<AttemptSummary[]> {
    const item = findCase(await getCases(runId), caseId);
    if (!item) return [];
    const attempts = await apiRequest<AttemptDetail[]>(
      `${runPath(runId)}/cases/${encodeURIComponent(item.case_execution_id)}/attempts`
    );
    return attempts.map(toAttemptSummary);
  },

  /** The current backend does not expose observations from the run API yet. */
  getObservation(
    _runId: string,
    _caseId: string,
    _attemptId?: string
  ): Promise<TargetObservationDetail | null> {
    return Promise.resolve(null);
  },

  async getCaseMetrics(runId: string, caseId: string): Promise<MetricResultSummary[]> {
    const results = await getResults(runId);
    return results.metrics
      .filter((item) => item.case_id === caseId || item.case_execution_id === caseId)
      .map(toMetricResultSummary);
  },

  async getRunResults(runId: string): Promise<RunResultsResponse> {
    return getResults(runId);
  },

  async getRunAggregates(runId: string): Promise<AggregateResultSummary[]> {
    const results = await getResults(runId);
    return results.aggregates.map(toAggregateResultSummary);
  },

  async getRunReport(runId: string): Promise<RunReport> {
    const [run, progress, results] = await Promise.all([
      this.getRun(runId),
      this.getRunProgress(runId),
      getResults(runId),
    ]);
    const started = run.started_at ? new Date(run.started_at).getTime() : null;
    const finished = run.finished_at ? new Date(run.finished_at).getTime() : null;
    const duration =
      started !== null ? ((finished ?? Date.now()) - started) / 1000 : null;
    const grouped: Record<string, Record<string, unknown>> = {};
    for (const aggregate of results.aggregates) {
      const family = aggregate.metric_id.split(".")[0] ?? "other";
      grouped[family] ??= {};
      grouped[family][`${aggregate.metric_id}.${aggregate.aggregation}`] =
        aggregate.value;
    }
    return {
      run_id: run.run_id,
      run_name: run.name,
      status: run.status,
      target_id: run.target_id,
      config_hash: run.config_hash,
      total_cases: progress.total_cases,
      complete_cases: progress.complete_cases,
      failed_cases: progress.failed_cases,
      pending_cases: progress.pending_cases,
      answer_metrics: grouped.answer ?? {},
      retrieval_metrics: grouped.retrieval ?? {},
      citation_metrics: grouped.citation ?? {},
      performance_metrics: grouped.performance ?? {},
      usage_metrics: grouped.usage ?? {},
      cost_metrics: grouped.cost ?? {},
      reliability_metrics: grouped.reliability ?? {},
      started_at: run.started_at,
      finished_at: run.finished_at,
      duration_seconds: duration,
    };
  },

  async compareRuns(runAId: string, runBId: string): Promise<ComparisonResult> {
    const [runA, runB, resultsA, resultsB] = await Promise.all([
      this.getRun(runAId),
      this.getRun(runBId),
      getResults(runAId),
      getResults(runBId),
    ]);
    const valuesA = new Map(
      resultsA.aggregates.map((item) => [
        `${item.metric_id}:${item.metric_version}:${item.aggregation}`,
        item,
      ])
    );
    const valuesB = new Map(
      resultsB.aggregates.map((item) => [
        `${item.metric_id}:${item.metric_version}:${item.aggregation}`,
        item,
      ])
    );
    const keys = new Set([...valuesA.keys(), ...valuesB.keys()]);
    const comparisons = [...keys].map((key) => {
      const a = valuesA.get(key);
      const b = valuesB.get(key);
      const aValue = typeof a?.value === "number" ? a.value : null;
      const bValue = typeof b?.value === "number" ? b.value : null;
      const delta = aValue !== null && bValue !== null ? bValue - aValue : null;
      return {
        metric_id: a?.metric_id ?? b?.metric_id ?? key,
        metric_version: a?.metric_version ?? b?.metric_version ?? "1",
        aggregation: a?.aggregation ?? b?.aggregation ?? "",
        run_a_value: a?.value ?? null,
        run_b_value: b?.value ?? null,
        absolute_delta: delta,
        relative_delta_percent:
          delta !== null && aValue !== null && aValue !== 0
            ? (delta / aValue) * 100
            : null,
        direction: "neutral" as const,
        status:
          delta === null
            ? ("incomparable" as const)
            : delta === 0
              ? ("unchanged" as const)
              : ("improved" as const),
      };
    });
    return {
      run_a_id: runA.run_id,
      run_b_id: runB.run_id,
      compatibility_warnings:
        runA.config_hash === runB.config_hash
          ? []
          : ["Runs have different configurations."],
      metric_comparisons: comparisons,
      summary: {},
      compared_at: new Date().toISOString(),
    };
  },

  exportRun(_runId: string, _request: ExportRequest): Promise<ExportResult> {
    throw new Error("Run export is not available from the current API.");
  },
};
