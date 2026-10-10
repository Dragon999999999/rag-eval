/** HTTP client for persisted test runs and their metric results. */

import { apiRequest } from "@/lib/api/client";
import { API_BASE_URL } from "@/config/env";
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
  MetricRunDetail,
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

  async listMetricRuns(runId: string): Promise<MetricRunDetail[]> {
    return apiRequest<MetricRunDetail[]>(`${runPath(runId)}/metric-runs`);
  },

  async createMetricRun(
    runId: string,
    request: {
      name: string;
      config: Record<string, unknown>;
      execute?: boolean;
    }
  ): Promise<MetricRunDetail> {
    return apiRequest<MetricRunDetail>(`${runPath(runId)}/metric-runs`, {
      method: "POST",
      body: request,
    });
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

  async getObservation(
    runId: string,
    caseId: string,
    attemptId?: string
  ): Promise<TargetObservationDetail | null> {
    const item = findCase(await getCases(runId), caseId);
    if (!item) return null;

    const query = attemptId ? `?attempt_id=${encodeURIComponent(attemptId)}` : "";
    return apiRequest<TargetObservationDetail | null>(
      `${runPath(runId)}/cases/${encodeURIComponent(item.case_execution_id)}/observation${query}`
    );
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
    return apiRequest<RunReport>(`${runPath(runId)}/report`);
  },

  async compareRuns(runAId: string, runBId: string): Promise<ComparisonResult> {
    return apiRequest<ComparisonResult>(
      `${runPath(runAId)}/compare/${encodeURIComponent(runBId)}`
    );
  },

  async exportRun(runId: string, _request: ExportRequest): Promise<ExportResult> {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/bundles/runs/${encodeURIComponent(runId)}`
    );
    if (!response.ok) {
      throw new Error(
        `API error: ${String(response.status)} - ${await response.text()}`
      );
    }
    const blob = await response.blob();
    const downloadUrl = URL.createObjectURL(blob);
    return {
      run_id: runId,
      export_id: `bundle-${runId}`,
      status: "COMPLETED",
      files: [
        {
          filename: `${runId}.rzip`,
          format: "rzip",
          size_bytes: blob.size,
          download_url: downloadUrl,
        },
      ],
      download_url: downloadUrl,
      created_at: new Date().toISOString(),
    };
  },
};
