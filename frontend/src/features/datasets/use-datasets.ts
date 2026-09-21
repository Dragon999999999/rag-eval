/** TanStack Query hooks for benchmark retrieval and file uploads. */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { BenchmarkService } from "./dataset-service";
import type {
  BenchmarkCreate,
  BenchmarkDetail,
  BenchmarkFileCreate,
  BenchmarkInfo,
  DatasetValidationResult,
  PaginatedCases,
} from "./dataset-types";

export const benchmarkQueryKeys = {
  all: ["benchmarks"] as const,
  list: () => [...benchmarkQueryKeys.all, "list"] as const,
  detail: (benchmarkId: string) => [...benchmarkQueryKeys.all, benchmarkId] as const,
};

export const datasetQueryKeys = benchmarkQueryKeys;

export function useBenchmarkList(
  options?: Omit<UseQueryOptions<BenchmarkInfo[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: benchmarkQueryKeys.list(),
    queryFn: () => BenchmarkService.listBenchmarks(),
    ...options,
  });
}

export function useBenchmark(
  benchmarkId: string,
  options?: Omit<UseQueryOptions<BenchmarkDetail>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: benchmarkQueryKeys.detail(benchmarkId),
    queryFn: () => BenchmarkService.getBenchmark(benchmarkId),
    enabled: Boolean(benchmarkId),
    ...options,
  });
}

export function useCreateBenchmark(options?: {
  onSuccess?: (data: BenchmarkInfo) => void;
  onError?: (error: Error) => void;
}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: BenchmarkCreate) => BenchmarkService.createBenchmark(data),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: benchmarkQueryKeys.list() });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

export function useCreateBenchmarkFromFiles(options?: {
  onSuccess?: (data: BenchmarkInfo) => void;
  onError?: (error: Error) => void;
}) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: BenchmarkFileCreate) =>
      BenchmarkService.createBenchmarkFromFiles(data),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: benchmarkQueryKeys.list() });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

function useBenchmarkUpload(
  benchmarkId: string,
  upload: (id: string, files: File[]) => Promise<BenchmarkInfo>,
  options?: {
    onSuccess?: (data: BenchmarkInfo) => void;
    onError?: (error: Error) => void;
  }
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (files: File[]) => upload(benchmarkId, files),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({
        queryKey: benchmarkQueryKeys.detail(benchmarkId),
      });
      void queryClient.invalidateQueries({ queryKey: benchmarkQueryKeys.list() });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

export function useAddBenchmarkCases(
  benchmarkId: string,
  options?: {
    onSuccess?: (data: BenchmarkInfo) => void;
    onError?: (error: Error) => void;
  }
) {
  return useBenchmarkUpload(
    benchmarkId,
    (id, files) => BenchmarkService.addCases(id, files),
    options
  );
}

export function useAddBenchmarkDocuments(
  benchmarkId: string,
  options?: {
    onSuccess?: (data: BenchmarkInfo) => void;
    onError?: (error: Error) => void;
  }
) {
  return useBenchmarkUpload(
    benchmarkId,
    (id, files) => BenchmarkService.addDocuments(id, files),
    options
  );
}

export function useAddBenchmarkChunks(
  benchmarkId: string,
  options?: {
    onSuccess?: (data: BenchmarkInfo) => void;
    onError?: (error: Error) => void;
  }
) {
  return useBenchmarkUpload(
    benchmarkId,
    (id, files) => BenchmarkService.addChunks(id, files),
    options
  );
}

// Compatibility hook names for existing test-builder code.
export const useDatasetList = useBenchmarkList;
export const useDataset = useBenchmark;
export const useCaseList = (
  benchmarkId: string,
  params?: { limit?: number; offset?: number; search?: string; tag?: string },
  options?: Omit<UseQueryOptions<PaginatedCases>, "queryKey" | "queryFn">
) =>
  useQuery({
    queryKey: [...benchmarkQueryKeys.detail(benchmarkId), "cases", params] as const,
    queryFn: () => BenchmarkService.listCases(benchmarkId, params),
    enabled: Boolean(benchmarkId),
    ...options,
  });
export const useCase = (benchmarkId: string, caseId: string) =>
  useQuery({
    queryKey: [...benchmarkQueryKeys.detail(benchmarkId), "case", caseId] as const,
    queryFn: () => BenchmarkService.getCase(benchmarkId, caseId),
    enabled: Boolean(benchmarkId && caseId),
  });

/** Deprecated no-op compatibility hook; benchmarks are append-only via uploads. */
export function useValidateDataset(options?: {
  onSuccess?: (data: DatasetValidationResult) => void;
}) {
  return useMutation({
    mutationFn: async (benchmarkId: string): Promise<DatasetValidationResult> => {
      const detail = await BenchmarkService.getBenchmark(benchmarkId);
      const total = detail.cases.length;
      return {
        benchmark_id: benchmarkId,
        valid: detail.cases.every((item) => item.query.trim().length > 0),
        total_cases: total,
        valid_cases: detail.cases.filter((item) => item.query.trim().length > 0).length,
        invalid_cases: detail.cases.filter((item) => item.query.trim().length === 0)
          .length,
        errors: [],
      };
    },
    onSuccess: options?.onSuccess,
  });
}
