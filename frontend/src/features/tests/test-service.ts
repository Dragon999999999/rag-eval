/** HTTP clients for the persisted test-definition and run APIs. */

import { apiRequest } from "@/lib/api/client";
import { API_BASE_URL } from "@/config/env";
import type {
  EvaluationRunSummary,
  MetricDefinition,
  MetricImportResult,
  RunStatusResponse,
  TestDefinitionCreate,
  TestDefinitionInfo,
  TestDefinitionUpdate,
  TestMetricsInfo,
  ValidationResult,
} from "./test-types";

const testsPath = "/api/v1/tests";

function metricName(metricId: string): string {
  return (
    metricId
      .split(".")
      .at(-1)
      ?.split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ") ?? metricId
  );
}

function metricRequirements(value: MetricDefinition["requirements"]): string[] {
  return value.map((requirement) =>
    typeof requirement === "string"
      ? requirement
      : typeof (requirement.name ?? requirement.requirement) === "string"
        ? ((requirement.name ?? requirement.requirement) as string)
        : "requirement"
  );
}

export const TestService = {
  async listTests(): Promise<TestDefinitionInfo[]> {
    return apiRequest<TestDefinitionInfo[]>(testsPath);
  },

  async getTest(testId: string): Promise<TestDefinitionInfo> {
    return apiRequest<TestDefinitionInfo>(`${testsPath}/${encodeURIComponent(testId)}`);
  },

  async createTest(data: TestDefinitionCreate): Promise<TestDefinitionInfo> {
    return apiRequest<TestDefinitionInfo>(testsPath, {
      method: "POST",
      body: {
        name: data.name,
        description: data.description ?? null,
        metadata: data.metadata ?? {},
      },
    });
  },

  async updateTest(
    testId: string,
    data: TestDefinitionUpdate
  ): Promise<TestDefinitionInfo> {
    return apiRequest<TestDefinitionInfo>(
      `${testsPath}/${encodeURIComponent(testId)}`,
      { method: "PATCH", body: data }
    );
  },

  async deleteTest(testId: string): Promise<void> {
    await apiRequest<undefined>(`${testsPath}/${encodeURIComponent(testId)}`, {
      method: "DELETE",
    });
  },

  async getTestMetrics(testId: string): Promise<TestMetricsInfo> {
    return apiRequest<TestMetricsInfo>(
      `${testsPath}/${encodeURIComponent(testId)}/metrics`
    );
  },

  async setTestMetrics(
    testId: string,
    data: {
      mode: "EXPLICIT" | "ALL_AVAILABLE";
      selected_metrics?: string[];
      metric_parameters?: Record<string, Record<string, unknown>>;
      judge_config?: Record<string, unknown>;
      retrieval_config?: Record<string, unknown>;
    }
  ): Promise<TestMetricsInfo> {
    return apiRequest<TestMetricsInfo>(
      `${testsPath}/${encodeURIComponent(testId)}/metrics`,
      { method: "PUT", body: data }
    );
  },

  async selectAllMetrics(testId: string): Promise<TestMetricsInfo> {
    return apiRequest<TestMetricsInfo>(
      `${testsPath}/${encodeURIComponent(testId)}/metrics/select-all`,
      { method: "POST" }
    );
  },

  async importTestYaml(testId: string, file: File): Promise<MetricImportResult> {
    const body = new FormData();
    body.append("file", file, file.name);
    return apiRequest<MetricImportResult>(
      `${testsPath}/${encodeURIComponent(testId)}/metrics/import`,
      { method: "POST", body }
    );
  },

  async exportTestYaml(testId: string): Promise<string> {
    const response = await fetch(
      `${API_BASE_URL}${testsPath}/${encodeURIComponent(testId)}/metrics/export`,
      { headers: { Accept: "application/yaml" } }
    );
    if (!response.ok) {
      throw new Error(
        `API error: ${String(response.status)} - ${await response.text()}`
      );
    }
    return response.text();
  },

  async validateTest(testId: string): Promise<ValidationResult> {
    return apiRequest<ValidationResult>(
      `${testsPath}/${encodeURIComponent(testId)}/validate`,
      { method: "POST" }
    );
  },

  async startRun(testId: string): Promise<EvaluationRunSummary> {
    return apiRequest<EvaluationRunSummary>(
      `${testsPath}/${encodeURIComponent(testId)}/runs`,
      { method: "POST" }
    );
  },

  async listRunsForTest(testId: string): Promise<EvaluationRunSummary[]> {
    return apiRequest<EvaluationRunSummary[]>(
      `${testsPath}/${encodeURIComponent(testId)}/runs`
    );
  },

  async getRun(runId: string): Promise<EvaluationRunSummary> {
    return apiRequest<EvaluationRunSummary>(
      `${testsPath}/runs/${encodeURIComponent(runId)}`
    );
  },

  async getRunStatus(runId: string): Promise<RunStatusResponse> {
    return apiRequest<RunStatusResponse>(
      `${testsPath}/runs/${encodeURIComponent(runId)}/status`
    );
  },

  async pauseRun(runId: string): Promise<EvaluationRunSummary> {
    return apiRequest<EvaluationRunSummary>(
      `${testsPath}/runs/${encodeURIComponent(runId)}/pause`,
      { method: "POST" }
    );
  },

  async resumeRun(runId: string): Promise<EvaluationRunSummary> {
    return apiRequest<EvaluationRunSummary>(
      `${testsPath}/runs/${encodeURIComponent(runId)}/resume`,
      { method: "POST" }
    );
  },

  async recoverRun(runId: string): Promise<EvaluationRunSummary> {
    return apiRequest<EvaluationRunSummary>(
      `${testsPath}/runs/${encodeURIComponent(runId)}/recover`,
      { method: "POST" }
    );
  },

  async cancelRun(runId: string): Promise<EvaluationRunSummary> {
    return apiRequest<EvaluationRunSummary>(
      `${testsPath}/runs/${encodeURIComponent(runId)}/cancel`,
      { method: "POST" }
    );
  },

  /** Compatibility helper for the retired draft builder. */
  validateDraft(data: TestDefinitionCreate): ValidationResult {
    const errors: string[] = [];
    if (!data.name.trim()) errors.push("Test name is required");
    if (!data.target_id) errors.push("Target must be selected");
    if (!data.benchmark_id) errors.push("Benchmark must be selected");
    return {
      valid: errors.length === 0,
      configuration_status: errors.length === 0 ? "READY" : "INCOMPLETE",
      target_valid: Boolean(data.target_id),
      benchmark_valid: Boolean(data.benchmark_id),
      metrics_valid: Boolean(data.metric_config_id),
      resolved_metric_ids: [],
      errors,
      warnings: [],
    };
  },
};

/** Registry adapter retained for existing metric-only consumers. */
export const MetricService = {
  async listMetrics(): Promise<MetricDefinition[]> {
    const definitions = await apiRequest<MetricDefinition[]>(
      `${testsPath}/metrics/registry`
    );
    return definitions.map((definition) => ({
      ...definition,
      display_name: metricName(definition.metric_id),
      requirements: metricRequirements(definition.requirements),
    }));
  },

  async getMetric(
    metricId: string,
    version = "1"
  ): Promise<MetricDefinition | undefined> {
    try {
      const definition = await apiRequest<MetricDefinition>(
        `${testsPath}/metrics/registry/${encodeURIComponent(metricId)}`
      );
      return {
        ...definition,
        version: definition.version || version,
        display_name: metricName(definition.metric_id),
        requirements: metricRequirements(definition.requirements),
      };
    } catch {
      return undefined;
    }
  },

  async getMetricsByCategory(_category: string): Promise<MetricDefinition[]> {
    return this.listMetrics();
  },

  checkCompatibility(): { compatible: boolean; reason?: string } {
    return { compatible: true };
  },

  getOrCreateMetricConfig(data: {
    name: string;
    selected_metrics: string[];
  }): Promise<{ metric_config_id: string; created: boolean }> {
    return Promise.resolve({
      metric_config_id: `${data.name}:${data.selected_metrics.join(",")}`,
      created: false,
    });
  },
};
