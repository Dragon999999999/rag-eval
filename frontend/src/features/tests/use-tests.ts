/** TanStack Query hooks for persisted tests and run lifecycle operations. */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { TestService, MetricService } from "./test-service";
import type {
  CreateRunRequest,
  EvaluationRunSummary,
  MetricDefinition,
  MetricImportResult,
  TestDefinitionCreate,
  TestDefinitionUpdate,
  ValidationResult,
} from "./test-types";

interface TestPlanEstimate {
  estimated_cases: number;
  estimated_requests: number;
}

export const testKeys = {
  all: ["tests"] as const,
  lists: () => [...testKeys.all, "list"] as const,
  details: () => [...testKeys.all, "detail"] as const,
  detail: (testId: string) => [...testKeys.details(), testId] as const,
  metrics: (testId: string) => [...testKeys.detail(testId), "metrics"] as const,
  validation: (testId: string) => [...testKeys.detail(testId), "validation"] as const,
  runs: (testId: string) => [...testKeys.detail(testId), "runs"] as const,
  run: (runId: string) => ["test-runs", runId] as const,
  status: (runId: string) => [...testKeys.run(runId), "status"] as const,
};

export const metricKeys = {
  all: ["metrics"] as const,
  lists: () => [...metricKeys.all, "list"] as const,
  list: (filters: Record<string, unknown>) => [...metricKeys.lists(), filters] as const,
  detail: (metricId: string, version?: string) =>
    [...metricKeys.all, "detail", metricId, version ?? "1"] as const,
  categories: () => [...metricKeys.all, "categories"] as const,
  compatibility: () => [...metricKeys.all, "compatibility"] as const,
};

export function useTests() {
  return useQuery({
    queryKey: testKeys.lists(),
    queryFn: () => TestService.listTests(),
  });
}

export function useTest(testId: string) {
  return useQuery({
    queryKey: testKeys.detail(testId),
    queryFn: () => TestService.getTest(testId),
    enabled: Boolean(testId),
  });
}

export function useTestMetrics(testId: string) {
  return useQuery({
    queryKey: testKeys.metrics(testId),
    queryFn: () => TestService.getTestMetrics(testId),
    enabled: Boolean(testId),
  });
}

export function useTestValidation(testId: string, enabled = true) {
  return useQuery({
    queryKey: testKeys.validation(testId),
    queryFn: () => TestService.validateTest(testId),
    enabled: Boolean(testId) && enabled,
    staleTime: 0,
  });
}

export function useTestRuns(testId: string) {
  return useQuery({
    queryKey: testKeys.runs(testId),
    queryFn: () => TestService.listRunsForTest(testId),
    enabled: Boolean(testId),
  });
}

export function useRun(runId: string) {
  return useQuery({
    queryKey: testKeys.run(runId),
    queryFn: () => TestService.getRun(runId),
    enabled: Boolean(runId),
  });
}

const activeRunStatuses = new Set([
  "PENDING",
  "QUEUED",
  "RUNNING",
  "PAUSING",
  "PAUSED",
  "INTERRUPTED",
  "pending",
  "queued",
  "running",
  "paused",
]);

export function isActiveRunStatus(status: string | undefined): boolean {
  return Boolean(status && activeRunStatuses.has(status));
}

export function isPersistentRunStatus(status: string | undefined): boolean {
  return (
    status === "PENDING" ||
    status === "QUEUED" ||
    status === "RUNNING" ||
    status === "PAUSING" ||
    status === "pending" ||
    status === "queued" ||
    status === "running"
  );
}

export function useRunStatus(runId: string) {
  return useQuery({
    queryKey: testKeys.status(runId),
    queryFn: () => TestService.getRunStatus(runId),
    enabled: Boolean(runId),
    refetchInterval: (query) =>
      isActiveRunStatus(query.state.data?.status) ? 2000 : false,
  });
}

function invalidateTest(client: ReturnType<typeof useQueryClient>, testId: string) {
  void client.invalidateQueries({ queryKey: testKeys.detail(testId) });
  void client.invalidateQueries({ queryKey: testKeys.lists() });
  void client.invalidateQueries({ queryKey: testKeys.metrics(testId) });
  void client.invalidateQueries({ queryKey: testKeys.validation(testId) });
}

export function useCreateTest() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: TestDefinitionCreate) => TestService.createTest(data),
    onSuccess: (test) => {
      client.setQueryData(testKeys.detail(test.test_definition_id), test);
      void client.invalidateQueries({ queryKey: testKeys.lists() });
    },
  });
}

export function useUpdateTest(testId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: TestDefinitionUpdate) => TestService.updateTest(testId, data),
    onSuccess: (test) => {
      client.setQueryData(testKeys.detail(testId), test);
      invalidateTest(client, testId);
    },
  });
}

export function useDeleteTest() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (testId: string) => TestService.deleteTest(testId),
    onSuccess: (_, testId) => {
      client.removeQueries({ queryKey: testKeys.detail(testId) });
      void client.invalidateQueries({ queryKey: testKeys.lists() });
    },
  });
}

export function useSetTestMetrics(testId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: Parameters<typeof TestService.setTestMetrics>[1]) =>
      TestService.setTestMetrics(testId, data),
    onSuccess: (metrics) => {
      client.setQueryData(testKeys.metrics(testId), metrics);
      invalidateTest(client, testId);
    },
  });
}

export function useSelectAllMetrics(testId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => TestService.selectAllMetrics(testId),
    onSuccess: (metrics) => {
      client.setQueryData(testKeys.metrics(testId), metrics);
      invalidateTest(client, testId);
    },
  });
}

export function useImportTestYaml(testId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (file: File): Promise<MetricImportResult> =>
      TestService.importTestYaml(testId, file),
    onSuccess: () => {
      invalidateTest(client, testId);
    },
  });
}

export function useStartTestRun(testId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => TestService.startRun(testId),
    onSuccess: (run) => {
      client.setQueryData(testKeys.run(run.run_id), run);
      void client.invalidateQueries({ queryKey: testKeys.runs(testId) });
      void client.invalidateQueries({ queryKey: testKeys.validation(testId) });
    },
  });
}

function useRunAction(
  action: (runId: string) => Promise<EvaluationRunSummary>,
  runId: string,
  testId?: string
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => action(runId),
    onSuccess: (run) => {
      client.setQueryData(testKeys.run(runId), run);
      void client.invalidateQueries({ queryKey: testKeys.status(runId) });
      if (testId) void client.invalidateQueries({ queryKey: testKeys.runs(testId) });
    },
  });
}

export function usePauseRun(runId: string, testId?: string) {
  return useRunAction((id) => TestService.pauseRun(id), runId, testId);
}
export function useResumeRun(runId: string, testId?: string) {
  return useRunAction((id) => TestService.resumeRun(id), runId, testId);
}
export function useRecoverRun(runId: string, testId?: string) {
  return useRunAction((id) => TestService.recoverRun(id), runId, testId);
}
export function useCancelRun(runId: string, testId?: string) {
  return useRunAction((id) => TestService.cancelRun(id), runId, testId);
}

/** Registry query retained for non-test metric consumers. */
export function useMetrics(
  options?: Omit<UseQueryOptions<MetricDefinition[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: metricKeys.lists(),
    queryFn: () => MetricService.listMetrics(),
    ...options,
  });
}

export function useMetric(metricId: string, version = "1") {
  return useQuery({
    queryKey: metricKeys.detail(metricId, version),
    queryFn: () => MetricService.getMetric(metricId, version),
    enabled: Boolean(metricId),
  });
}

export function useMetricsByCategory(category: string) {
  return useQuery({
    queryKey: metricKeys.list({ category }),
    queryFn: () => MetricService.getMetricsByCategory(category),
    enabled: Boolean(category),
  });
}

export function useMetricCompatibility() {
  return useMutation<
    { compatible: boolean },
    Error,
    {
      metricId: string;
      targetCapabilities: Record<string, boolean>;
      datasetFeatures: Record<string, boolean>;
    }
  >({
    mutationFn: (_request: {
      metricId: string;
      targetCapabilities: Record<string, boolean>;
      datasetFeatures: Record<string, boolean>;
    }) => Promise.resolve({ compatible: true }),
  });
}

/** Compatibility hook for the retired draft builder. */
export function useValidateTest() {
  return useMutation<ValidationResult, Error, TestDefinitionCreate>({
    mutationFn: (data: TestDefinitionCreate) =>
      Promise.resolve(TestService.validateDraft(data)),
  });
}

export function usePlanTest() {
  return useMutation<TestPlanEstimate, Error, TestDefinitionCreate>({
    mutationFn: (_data: TestDefinitionCreate) =>
      Promise.resolve({
        estimated_cases: 0,
        estimated_requests: 0,
      }),
  });
}

export function useRunTest() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateRunRequest) => {
      if (!data.test_definition_id) throw new Error("test_definition_id is required");
      return TestService.startRun(data.test_definition_id);
    },
    onSuccess: (run, variables) => {
      if (variables.test_definition_id) {
        void client.invalidateQueries({
          queryKey: testKeys.runs(variables.test_definition_id),
        });
      }
      client.setQueryData(testKeys.run(run.run_id), run);
    },
  });
}

export function useGetOrCreateMetricConfig() {
  return useMutation({
    mutationFn: (data: { name: string; selected_metrics: string[] }) =>
      MetricService.getOrCreateMetricConfig(data),
  });
}
