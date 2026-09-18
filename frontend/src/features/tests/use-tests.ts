/**
 * TanStack Query hooks for TestDefinition and Metric operations.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { TestService, MetricService } from "./test-service";
import type {
  TestDefinitionCreate,
  TestDefinitionUpdate,
  CreateRunRequest,
} from "./test-types";

/** Query key factories for type-safe cache management */
export const testKeys = {
  all: ["tests"] as const,
  lists: () => [...testKeys.all, "list"] as const,
  list: (filters: Record<string, unknown>) => [...testKeys.lists(), filters] as const,
  details: () => [...testKeys.all, "detail"] as const,
  detail: (testId: string) => [...testKeys.details(), testId] as const,
  runs: (testId: string) => [...testKeys.detail(testId), "runs"] as const,
  plan: () => [...testKeys.all, "plan"] as const,
  validate: () => [...testKeys.all, "validate"] as const,
};

export const metricKeys = {
  all: ["metrics"] as const,
  lists: () => [...metricKeys.all, "list"] as const,
  list: (filters: Record<string, unknown>) => [...metricKeys.lists(), filters] as const,
  detail: (metricId: string, version?: string) =>
    [...metricKeys.all, "detail", metricId, version ?? "1.0"] as const,
  categories: () => [...metricKeys.all, "categories"] as const,
  compatibility: () => [...metricKeys.all, "compatibility"] as const,
};

/**
 * Hook to list all test definitions.
 */
export function useTests() {
  return useQuery({
    queryKey: testKeys.lists(),
    queryFn: () => TestService.listTests(),
  });
}

/**
 * Hook to get a single test definition by ID.
 */
export function useTest(testId: string) {
  return useQuery({
    queryKey: testKeys.detail(testId),
    queryFn: () => TestService.getTest(testId),
    enabled: !!testId,
  });
}

/**
 * Hook to create a new test definition.
 */
export function useCreateTest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: TestDefinitionCreate) => TestService.createTest(data),
    onSuccess: (newTest) => {
      // Invalidate lists to trigger refetch
      void queryClient.invalidateQueries({ queryKey: testKeys.lists() });
      // Prefetch the detail
      void queryClient.prefetchQuery({
        queryKey: testKeys.detail(newTest.test_definition_id),
        queryFn: () => TestService.getTest(newTest.test_definition_id),
      });
    },
  });
}

/**
 * Hook to update a test definition.
 */
export function useUpdateTest(testId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: TestDefinitionUpdate) => TestService.updateTest(testId, data),
    onSuccess: (updatedTest) => {
      // Update the detail cache
      queryClient.setQueryData(testKeys.detail(testId), updatedTest);
      // Invalidate lists
      void queryClient.invalidateQueries({ queryKey: testKeys.lists() });
    },
  });
}

/**
 * Hook to delete a test definition.
 */
export function useDeleteTest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (testId: string) => TestService.deleteTest(testId),
    onSuccess: (_, deletedId) => {
      // Remove from cache
      void queryClient.removeQueries({ queryKey: testKeys.detail(deletedId) });
      // Invalidate lists
      void queryClient.invalidateQueries({ queryKey: testKeys.lists() });
    },
  });
}

/**
 * Hook to validate a test definition (draft).
 */
export function useValidateTest() {
  return useMutation({
    mutationFn: (data: TestDefinitionCreate) => TestService.validateTest(data),
  });
}

/**
 * Hook to plan a test definition (get execution estimate).
 */
export function usePlanTest() {
  return useMutation({
    mutationFn: (data: TestDefinitionCreate) => TestService.planTest(data),
  });
}

/**
 * Hook to create/run a new evaluation run from a test definition.
 */
export function useRunTest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateRunRequest) => TestService.runTest(data),
    onSuccess: (_, variables) => {
      // Invalidate runs list for the test
      if (variables.test_definition_id) {
        void queryClient.invalidateQueries({
          queryKey: testKeys.runs(variables.test_definition_id),
        });
      }
    },
  });
}

/**
 * Hook to get an evaluation run summary.
 */
export function useRun(runId: string) {
  return useQuery({
    queryKey: ["runs", runId],
    queryFn: () => TestService.getRun(runId),
    enabled: !!runId,
    // Auto-refresh for running runs
    refetchInterval: (query) => {
      const run = query.state.data;
      return run?.status === "running" ? 5000 : false;
    },
  });
}

/**
 * Hook to list runs for a test definition.
 */
export function useTestRuns(testId: string) {
  return useQuery({
    queryKey: testKeys.runs(testId),
    queryFn: () => TestService.listRunsForTest(testId),
    enabled: !!testId,
  });
}

/**
 * Hook to list all available metrics.
 */
export function useMetrics() {
  return useQuery({
    queryKey: metricKeys.lists(),
    queryFn: () => MetricService.listMetrics(),
  });
}

/**
 * Hook to get a single metric definition.
 */
export function useMetric(metricId: string, version = "1.0") {
  return useQuery({
    queryKey: metricKeys.detail(metricId, version),
    queryFn: () => MetricService.getMetric(metricId, version),
    enabled: !!metricId,
  });
}

/**
 * Hook to get metrics by category.
 */
export function useMetricsByCategory(category: string) {
  return useQuery({
    queryKey: metricKeys.list({ category }),
    queryFn: () => MetricService.getMetricsByCategory(category),
    enabled: !!category,
  });
}

/**
 * Hook to check metric compatibility.
 */
export function useMetricCompatibility() {
  return useMutation({
    mutationFn: ({
      metricId,
      targetCapabilities,
      datasetFeatures,
    }: {
      metricId: string;
      targetCapabilities: Record<string, boolean>;
      datasetFeatures: Record<string, boolean>;
    }) => MetricService.checkCompatibility(metricId, targetCapabilities, datasetFeatures),
  });
}

/**
 * Hook to create or get a metric config.
 */
export function useGetOrCreateMetricConfig() {
  return useMutation({
    mutationFn: (data: {
      name: string;
      selected_metrics: string[];
      metric_parameters?: Record<string, unknown>;
    }) => MetricService.getOrCreateMetricConfig(data),
  });
}
