/**
 * TanStack Query hooks for EvaluationRun operations.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { ExportRequest } from "./run-types";
import { RunService } from "./run-service";

/** Query key factories for type-safe cache management */
export const runKeys = {
  all: ["runs"] as const,
  lists: () => [...runKeys.all, "list"] as const,
  list: (filters?: Record<string, unknown>) => [...runKeys.lists(), filters] as const,
  details: () => [...runKeys.all, "detail"] as const,
  detail: (runId: string) => [...runKeys.details(), runId] as const,
  progress: (runId: string) => [...runKeys.detail(runId), "progress"] as const,
  cases: (runId: string) => [...runKeys.detail(runId), "cases"] as const,
  caseList: (runId: string, filters?: Record<string, unknown>) =>
    [...runKeys.cases(runId), "list", filters] as const,
  case: (runId: string, caseId: string) => [...runKeys.cases(runId), "case", caseId] as const,
  attempts: (runId: string, caseId: string) =>
    [...runKeys.case(runId, caseId), "attempts"] as const,
  attempt: (runId: string, caseId: string, attemptId: string) =>
    [...runKeys.attempts(runId, caseId), "attempt", attemptId] as const,
  observation: (runId: string, caseId: string, attemptId?: string) =>
    [...runKeys.case(runId, caseId), "observation", attemptId ?? "latest"] as const,
  metrics: (runId: string, caseId: string) =>
    [...runKeys.case(runId, caseId), "metrics"] as const,
  aggregates: (runId: string) => [...runKeys.detail(runId), "aggregates"] as const,
  report: (runId: string) => [...runKeys.detail(runId), "report"] as const,
  comparison: (runAId: string, runBId: string) =>
    [...runKeys.all, "comparison", runAId, runBId] as const,
  export: (runId: string) => [...runKeys.detail(runId), "export"] as const,
};

/** Hook to list runs with filters */
export function useRunList(filters?: {
  status?: string;
  test_definition_id?: string;
  target_id?: string;
  benchmark_id?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: runKeys.list(filters),
    queryFn: () => RunService.listRuns(filters),
  });
}

/** Hook to get detailed run information */
export function useRun(runId: string) {
  return useQuery({
    queryKey: runKeys.detail(runId),
    queryFn: () => RunService.getRun(runId),
    enabled: !!runId,
  });
}

/** Hook to get run progress */
export function useRunProgress(runId: string, options?: { refetchInterval?: number | false }) {
  return useQuery({
    queryKey: runKeys.progress(runId),
    queryFn: () => RunService.getRunProgress(runId),
    enabled: !!runId,
    ...options,
  });
}

/** Hook to cancel a run */
export function useCancelRun() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (runId: string) => {
      await RunService.cancelRun(runId);
      return runId;
    },
    onSuccess: (runId) => {
      // Invalidate run detail and progress
      queryClient.invalidateQueries({ queryKey: runKeys.detail(runId) });
      queryClient.invalidateQueries({ queryKey: runKeys.progress(runId) });
      queryClient.invalidateQueries({ queryKey: runKeys.lists() });
    },
  });
}

/** Hook to get cases for a run */
export function useRunCases(runId: string, filters?: {
  limit?: number;
  offset?: number;
  status?: string;
  search?: string;
  tags?: string[];
  answerability?: string;
}) {
  return useQuery({
    queryKey: runKeys.caseList(runId, filters),
    queryFn: () => RunService.getRunCases(runId, filters),
    enabled: !!runId,
  });
}

/** Hook to get detailed case execution */
export function useRunCase(runId: string, caseId: string) {
  return useQuery({
    queryKey: runKeys.case(runId, caseId),
    queryFn: () => RunService.getRunCase(runId, caseId),
    enabled: !!runId && !!caseId,
  });
}

/** Hook to get attempts for a case */
export function useCaseAttempts(runId: string, caseId: string) {
  return useQuery({
    queryKey: runKeys.attempts(runId, caseId),
    queryFn: () => RunService.getCaseAttempts(runId, caseId),
    enabled: !!runId && !!caseId,
  });
}

/** Hook to get target observation */
export function useObservation(runId: string, caseId: string, attemptId?: string) {
  return useQuery({
    queryKey: runKeys.observation(runId, caseId, attemptId),
    queryFn: () => RunService.getObservation(runId, caseId, attemptId),
    enabled: !!runId && !!caseId,
  });
}

/** Hook to get case metrics */
export function useCaseMetrics(runId: string, caseId: string) {
  return useQuery({
    queryKey: runKeys.metrics(runId, caseId),
    queryFn: () => RunService.getCaseMetrics(runId, caseId),
    enabled: !!runId && !!caseId,
  });
}

/** Hook to get run aggregate metrics */
export function useRunAggregates(runId: string) {
  return useQuery({
    queryKey: runKeys.aggregates(runId),
    queryFn: () => RunService.getRunAggregates(runId),
    enabled: !!runId,
  });
}

/** Hook to get run report */
export function useRunReport(runId: string) {
  return useQuery({
    queryKey: runKeys.report(runId),
    queryFn: () => RunService.getRunReport(runId),
    enabled: !!runId,
  });
}

/** Hook to compare two runs */
export function useRunComparison(runAId: string, runBId: string) {
  return useQuery({
    queryKey: runKeys.comparison(runAId, runBId),
    queryFn: () => RunService.compareRuns(runAId, runBId),
    enabled: !!runAId && !!runBId,
  });
}

/** Hook to export a run */
export function useExportRun() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ runId, request }: { runId: string; request: ExportRequest }) => {
      return await RunService.exportRun(runId, request);
    },
    onSuccess: (_, { runId }) => {
      queryClient.invalidateQueries({ queryKey: runKeys.detail(runId) });
    },
  });
}
