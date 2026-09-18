/**
 * Test and Metric service API clients.
 *
 * Centralized services for TestDefinition and Metric operations.
 * Uses mock implementation - replace with real HTTP calls when backend is available.
 */
import type {
  TestDefinitionInfo,
  TestDefinitionCreate,
  TestDefinitionUpdate,
  TestDefinitionPlan,
  ValidationResult,
  EvaluationRunSummary,
  CreateRunRequest,
  MetricDefinition,
} from "./test-types";

const MOCK_DELAY_MS = 400;

/** Error with code and status properties */
interface ServiceError extends Error {
  code?: string;
  status?: number;
}

/** In-memory mock test store */
const mockTests = new Map<string, TestDefinitionInfo>();
const mockRuns = new Map<string, EvaluationRunSummary>();

/** Mock metric registry - populated from backend metadata in real impl */
const mockMetrics: MetricDefinition[] = [
  // Retrieval metrics
  {
    metric_id: "retrieval.recall_at_k",
    version: "1.0",
    display_name: "Recall@K",
    description: "Measures whether gold evidence is retrieved in top-K results.",
    scope: "CASE",
    requirements: ["GOLD_EVIDENCE", "TARGET_RETRIEVAL"],
    category: "Retrieval",
    config_schema: {
      k_values: { type: "array", items: { type: "integer" }, default: [1, 5, 10] },
    },
  },
  {
    metric_id: "retrieval.mrr",
    version: "1.0",
    display_name: "MRR",
    description: "Mean Reciprocal Rank of first relevant retrieval.",
    scope: "CASE",
    requirements: ["GOLD_EVIDENCE", "TARGET_RETRIEVAL"],
    category: "Retrieval",
  },
  // Answer quality metrics
  {
    metric_id: "answer.exact_match",
    version: "1.0",
    display_name: "Exact Match",
    description: "Binary match between answer and reference.",
    scope: "CASE",
    requirements: ["REFERENCE_ANSWER"],
    category: "Answer Quality",
  },
  {
    metric_id: "answer.token_f1",
    version: "1.0",
    display_name: "Token F1",
    description: "Token-level F1 score between answer and reference.",
    scope: "CASE",
    requirements: ["REFERENCE_ANSWER"],
    category: "Answer Quality",
  },
  // Grounding metrics
  {
    metric_id: "grounding.citation_recall",
    version: "1.0",
    display_name: "Citation Recall",
    description: "Measures whether gold evidence is covered by citations.",
    scope: "CASE",
    requirements: ["GOLD_EVIDENCE", "TARGET_CITATIONS"],
    category: "Grounding",
  },
  {
    metric_id: "grounding.citation_precision",
    version: "1.0",
    display_name: "Citation Precision",
    description: "Measures whether citations are supported by evidence.",
    scope: "CASE",
    requirements: ["GOLD_EVIDENCE", "TARGET_CITATIONS"],
    category: "Grounding",
  },
  // Performance metrics
  {
    metric_id: "performance.total_latency_ms",
    version: "1.0",
    display_name: "Total Latency",
    description: "End-to-end latency in milliseconds.",
    scope: "CASE",
    requirements: ["TARGET_TRACE"],
    category: "Performance",
  },
  {
    metric_id: "performance.tokens_per_second",
    version: "1.0",
    display_name: "Tokens/Second",
    description: "Generation throughput in tokens per second.",
    scope: "CASE",
    requirements: ["TARGET_TRACE", "TARGET_USAGE"],
    category: "Performance",
  },
  // Usage metrics
  {
    metric_id: "usage.total_tokens",
    version: "1.0",
    display_name: "Total Tokens",
    description: "Total tokens consumed (input + output).",
    scope: "CASE",
    requirements: ["TARGET_USAGE"],
    category: "Usage",
  },
  // Reliability metrics
  {
    metric_id: "reliability.success_rate",
    version: "1.0",
    display_name: "Success Rate",
    description: "Percentage of cases completed without error.",
    scope: "RUN",
    requirements: ["RUN_METADATA"],
    category: "Reliability",
  },
];

/** Initialize with mock data */
function initializeMockData() {
  if (mockTests.size > 0) return;

  // Sample test definition
  const test1: TestDefinitionInfo = {
    test_definition_id: "test-001",
    name: "Grounding Regression",
    description: "Regular grounding evaluation for RAG v3",
    target_id: "target-http-001",
    benchmark_id: "dataset-qkd-001",
    metric_config_id: "mc-001",
    execution_config: {
      concurrency: 4,
      timeout_per_request: 30,
      retries: 2,
      failure_policy: "continue",
    },
    seed: 42,
    tags: ["regression", "grounding"],
    metadata: {},
    definition_hash: "sha256:abc123...",
    created_at: new Date(Date.now() - 86400000 * 7).toISOString(),
    updated_at: new Date(Date.now() - 86400000).toISOString(),
  };

  mockTests.set(test1.test_definition_id, test1);

  // Sample run
  const run1: EvaluationRunSummary = {
    run_id: "run-001",
    name: "Grounding Regression - Run #1",
    status: "completed",
    config_hash: "sha256:abc123...",
    target_id: "target-http-001",
    test_definition_id: "test-001",
    started_at: new Date(Date.now() - 3600000).toISOString(),
    finished_at: new Date(Date.now() - 1800000).toISOString(),
    created_at: new Date(Date.now() - 3600000).toISOString(),
    progress: {
      total_cases: 250,
      complete_cases: 248,
      failed_cases: 2,
      pending_cases: 0,
      percent: 100,
    },
  };

  mockRuns.set(run1.run_id, run1);
}

export const TestService = {
  /** List all test definitions */
  async listTests(): Promise<TestDefinitionInfo[]> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));
    return Array.from(mockTests.values()).sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    );
  },

  /** Get a single test definition */
  async getTest(testId: string): Promise<TestDefinitionInfo> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));
    const test = mockTests.get(testId);
    if (!test) {
      const error = new Error(`Test definition not found: ${testId}`);
      (error as ServiceError).code = "TEST_NOT_FOUND";
      (error as ServiceError).status = 404;
      throw error;
    }
    return test;
  },

  /** Create a new test definition */
  async createTest(data: TestDefinitionCreate): Promise<TestDefinitionInfo> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const testId = `test-${String(Date.now())}-${Math.random().toString(36).slice(2, 8)}`;
    const now = new Date().toISOString();

    const test: TestDefinitionInfo = {
      test_definition_id: testId,
      name: data.name,
      description: data.description ?? null,
      target_id: data.target_id,
      benchmark_id: data.benchmark_id,
      metric_config_id: data.metric_config_id,
      execution_config: data.execution_config ?? {},
      seed: data.seed ?? null,
      tags: data.tags ?? [],
      metadata: data.metadata ?? {},
      definition_hash: `sha256:${Math.random().toString(36).slice(2)}`,
      created_at: now,
      updated_at: now,
    };

    mockTests.set(testId, test);
    return test;
  },

  /** Update a test definition */
  async updateTest(
    testId: string,
    data: TestDefinitionUpdate
  ): Promise<TestDefinitionInfo> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const existing = mockTests.get(testId);
    if (!existing) {
      const error = new Error(`Test definition not found: ${testId}`);
      (error as ServiceError).code = "TEST_NOT_FOUND";
      (error as ServiceError).status = 404;
      throw error;
    }

    const updated: TestDefinitionInfo = {
      ...existing,
      name: data.name ?? existing.name,
      description: data.description ?? existing.description,
      target_id: data.target_id ?? existing.target_id,
      benchmark_id: data.benchmark_id ?? existing.benchmark_id,
      metric_config_id: data.metric_config_id ?? existing.metric_config_id,
      execution_config: data.execution_config ?? existing.execution_config,
      seed: data.seed ?? existing.seed,
      tags: data.tags ?? existing.tags,
      metadata: data.metadata ?? existing.metadata,
      updated_at: new Date().toISOString(),
    };

    mockTests.set(testId, updated);
    return updated;
  },

  /** Delete a test definition */
  async deleteTest(testId: string): Promise<void> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    if (!mockTests.has(testId)) {
      const error = new Error(`Test definition not found: ${testId}`);
      (error as ServiceError).code = "TEST_NOT_FOUND";
      (error as ServiceError).status = 404;
      throw error;
    }

    mockTests.delete(testId);
  },

  /** Validate a test definition */
  async validateTest(data: TestDefinitionCreate): Promise<ValidationResult> {
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS + 300));

    // Mock validation - check required fields
    const errors: string[] = [];
    const warnings: string[] = [];

    if (!data.name || data.name.trim().length === 0) {
      errors.push("Test name is required");
    }

    if (!data.target_id) {
      errors.push("Target must be selected");
    }

    if (!data.benchmark_id) {
      errors.push("Dataset must be selected");
    }

    if (!data.metric_config_id || !data.metric_config_id.startsWith("mc-")) {
      errors.push("At least one metric must be configured");
    }

    return {
      valid: errors.length === 0,
      structural_valid: errors.length === 0,
      capabilities_valid: errors.length === 0,
      errors,
      warnings,
    };
  },

  /** Plan a test definition (get execution estimate) */
  async planTest(data: TestDefinitionCreate): Promise<TestDefinitionPlan> {
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS + 500));

    // Mock plan - in real impl would call backend
    return {
      test_definition_id: "draft",
      name: data.name,
      description: data.description ?? null,
      target: { target_id: data.target_id },
      benchmark: { benchmark_id: data.benchmark_id, case_count: 250 },
      metric_config: { metric_config_id: data.metric_config_id },
      execution_config: data.execution_config ?? {},
      seed: data.seed ?? null,
      config_hash: `sha256:${Math.random().toString(36).slice(2)}`,
      tags: data.tags ?? [],
      experiment_config: {},
      estimated_cases: 250,
      estimated_requests: 250,
    };
  },

  /** Create/run a new evaluation run from test definition */
  async runTest(data: CreateRunRequest): Promise<EvaluationRunSummary> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS + 500));

    const runId = `run-${String(Date.now())}-${Math.random().toString(36).slice(2, 8)}`;
    const now = new Date().toISOString();

    const run: EvaluationRunSummary = {
      run_id: runId,
      name: data.name ?? `Run ${new Date().toLocaleDateString()}`,
      status: "queued",
      config_hash: `sha256:${Math.random().toString(36).slice(2)}`,
      target_id: null,
      test_definition_id: data.test_definition_id ?? null,
      started_at: null,
      finished_at: null,
      created_at: now,
      progress: {
        total_cases: 250,
        complete_cases: 0,
        failed_cases: 0,
        pending_cases: 250,
        percent: 0,
      },
    };

    mockRuns.set(runId, run);
    return run;
  },

  /** Get evaluation run summary */
  async getRun(runId: string): Promise<EvaluationRunSummary> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const run = mockRuns.get(runId);
    if (!run) {
      const error = new Error(`Run not found: ${runId}`);
      (error as ServiceError).code = "RUN_NOT_FOUND";
      (error as ServiceError).status = 404;
      throw error;
    }

    // Simulate progress for running runs
    if (run.status === "running") {
      const progress = run.progress ?? {
        total_cases: 250,
        complete_cases: 0,
        failed_cases: 0,
        pending_cases: 250,
        percent: 0,
      };
      run.progress = {
        ...progress,
        complete_cases: Math.min(
          progress.total_cases,
          progress.complete_cases + 10
        ),
        percent: Math.round(
          (progress.complete_cases / progress.total_cases) * 100
        ),
      };
    }

    return run;
  },

  /** List runs for a test definition */
  async listRunsForTest(testId: string): Promise<EvaluationRunSummary[]> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    return Array.from(mockRuns.values())
      .filter((run) => run.test_definition_id === testId)
      .sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
  },
};

export const MetricService = {
  /** List all available metrics from registry */
  async listMetrics(): Promise<MetricDefinition[]> {
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));
    return [...mockMetrics];
  },

  /** Get a single metric definition */
  async getMetric(
    metricId: string,
    version = "1.0"
  ): Promise<MetricDefinition | undefined> {
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));
    return mockMetrics.find((m) => m.metric_id === metricId && m.version === version);
  },

  /** Get metrics by category */
  async getMetricsByCategory(category: string): Promise<MetricDefinition[]> {
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));
    return mockMetrics.filter((m) => m.category === category);
  },

  /** Check metric compatibility with target/dataset */
  async checkCompatibility(
    metricId: string,
    targetCapabilities: Record<string, boolean>,
    datasetFeatures: Record<string, boolean>
  ): Promise<{ compatible: boolean; reason?: string }> {
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const metric = mockMetrics.find((m) => m.metric_id === metricId);
    if (!metric) {
      return { compatible: false, reason: "Metric not found" };
    }

    // Check requirements against capabilities
    const missingRequirements: string[] = [];

    for (const req of metric.requirements) {
      switch (req) {
        case "TARGET_CITATIONS":
          if (!targetCapabilities.citations) {
            missingRequirements.push("Target does not expose citations");
          }
          break;
        case "TARGET_CONFIDENCE":
          if (!targetCapabilities.confidence) {
            missingRequirements.push("Target does not expose confidence");
          }
          break;
        case "TARGET_TRACE":
          if (!targetCapabilities.trace) {
            missingRequirements.push("Target does not expose trace");
          }
          break;
        case "TARGET_USAGE":
          if (!targetCapabilities.usage) {
            missingRequirements.push("Target does not expose usage");
          }
          break;
        case "TARGET_RETRIEVAL":
          if (!targetCapabilities.retrieval) {
            missingRequirements.push("Target does not expose retrieval");
          }
          break;
        case "GOLD_EVIDENCE":
          if (!datasetFeatures.gold_evidence) {
            missingRequirements.push("Dataset has no gold evidence");
          }
          break;
        case "REFERENCE_ANSWER":
          if (!datasetFeatures.reference_answer) {
            missingRequirements.push("Dataset has no reference answers");
          }
          break;
      }
    }

    if (missingRequirements.length > 0) {
      return { compatible: false, reason: missingRequirements.join("; ") };
    }

    return { compatible: true };
  },

  /** Create or get metric config */
  async getOrCreateMetricConfig(_data: {
    name: string;
    selected_metrics: string[];
    metric_parameters?: Record<string, unknown>;
  }): Promise<{ metric_config_id: string; created: boolean }> {
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    // Mock - in real impl would check existing configs or create new
    const configId = `mc-${String(Date.now())}-${Math.random().toString(36).slice(2, 8)}`;
    return { metric_config_id: configId, created: true };
  },
};
