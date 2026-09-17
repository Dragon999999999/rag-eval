/**
 * TanStack Query hooks for dataset management.
 */
import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { DatasetService } from "./dataset-service";
import type {
  DatasetInfo,
  DatasetCreate,
  DatasetUpdate,
  BenchmarkCase,
  CaseCreate,
  CaseUpdate,
  PaginatedCases,
  DatasetValidationResult,
} from "./dataset-types";

/** Query key factory */
export const datasetQueryKeys = {
  all: ["datasets"] as const,
  lists: () => [...datasetQueryKeys.all, "list"] as const,
  list: (filters?: { search?: string; tag?: string }) =>
    [...datasetQueryKeys.lists(), filters] as const,
  details: () => [...datasetQueryKeys.all, "detail"] as const,
  detail: (datasetId: string) => [...datasetQueryKeys.details(), datasetId] as const,
  cases: (datasetId: string) =>
    [...datasetQueryKeys.detail(datasetId), "cases"] as const,
  caseList: (datasetId: string, filters?: { limit?: number; offset?: number; search?: string; tag?: string }) =>
    [...datasetQueryKeys.cases(datasetId), "list", filters] as const,
  case: (datasetId: string, caseId: string) =>
    [...datasetQueryKeys.cases(datasetId), "case", caseId] as const,
  validation: (datasetId: string) =>
    [...datasetQueryKeys.detail(datasetId), "validation"] as const,
};

/** Hook to list datasets */
export function useDatasetList(options?: Omit<UseQueryOptions<DatasetInfo[], Error>, "queryKey" | "queryFn">) {
  return useQuery({
    queryKey: datasetQueryKeys.list(),
    queryFn: () => DatasetService.listDatasets(),
    ...options,
  });
}

/** Hook to get a single dataset */
export function useDataset(datasetId: string, options?: Omit<UseQueryOptions<DatasetInfo, Error>, "queryKey" | "queryFn">) {
  return useQuery({
    queryKey: datasetQueryKeys.detail(datasetId),
    queryFn: () => DatasetService.getDataset(datasetId),
    enabled: !!datasetId,
    ...options,
  });
}

/** Hook to create a dataset */
export function useCreateDataset(options?: { onSuccess?: (data: DatasetInfo) => void; onError?: (error: Error) => void }) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: DatasetCreate) => DatasetService.createDataset(data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: datasetQueryKeys.lists() });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

/** Hook to update a dataset */
export function useUpdateDataset(
  datasetId: string,
  options?: { onSuccess?: (data: DatasetInfo) => void; onError?: (error: Error) => void }
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: DatasetUpdate) => DatasetService.updateDataset(datasetId, data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: datasetQueryKeys.detail(datasetId) });
      queryClient.invalidateQueries({ queryKey: datasetQueryKeys.lists() });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

/** Hook to delete a dataset */
export function useDeleteDataset(options?: { onSuccess?: () => void; onError?: (error: Error) => void }) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (datasetId: string) => {
      await DatasetService.deleteDataset(datasetId);
      return datasetId;
    },
    onSuccess: (datasetId) => {
      queryClient.removeQueries({ queryKey: datasetQueryKeys.detail(datasetId) });
      queryClient.invalidateQueries({ queryKey: datasetQueryKeys.lists() });
      options?.onSuccess?.();
    },
    onError: options?.onError,
  });
}

/** Hook to list cases with pagination */
export function useCaseList(
  datasetId: string,
  params?: { limit?: number; offset?: number; search?: string; tag?: string },
  options?: Omit<UseQueryOptions<PaginatedCases, Error>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: datasetQueryKeys.caseList(datasetId, params),
    queryFn: () => DatasetService.listCases(datasetId, params),
    enabled: !!datasetId,
    ...options,
  });
}

/** Hook to get a single case */
export function useCase(
  datasetId: string,
  caseId: string,
  options?: Omit<UseQueryOptions<BenchmarkCase, Error>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: datasetQueryKeys.case(datasetId, caseId),
    queryFn: () => DatasetService.getCase(datasetId, caseId),
    enabled: !!datasetId && !!caseId,
    ...options,
  });
}

/** Hook to create a case */
export function useCreateCase(
  datasetId: string,
  options?: { onSuccess?: (data: BenchmarkCase) => void; onError?: (error: Error) => void }
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CaseCreate) => DatasetService.createCase(datasetId, data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: datasetQueryKeys.cases(datasetId) });
      queryClient.invalidateQueries({ queryKey: datasetQueryKeys.detail(datasetId) });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

/** Hook to update a case */
export function useUpdateCase(
  datasetId: string,
  caseId: string,
  options?: { onSuccess?: (data: BenchmarkCase) => void; onError?: (error: Error) => void }
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CaseUpdate) => DatasetService.updateCase(datasetId, caseId, data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: datasetQueryKeys.case(datasetId, caseId) });
      queryClient.invalidateQueries({ queryKey: datasetQueryKeys.cases(datasetId) });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

/** Hook to delete a case */
export function useDeleteCase(
  datasetId: string,
  caseId: string,
  options?: { onSuccess?: () => void; onError?: (error: Error) => void }
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      await DatasetService.deleteCase(datasetId, caseId);
      return caseId;
    },
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: datasetQueryKeys.case(datasetId, caseId) });
      queryClient.invalidateQueries({ queryKey: datasetQueryKeys.cases(datasetId) });
      queryClient.invalidateQueries({ queryKey: datasetQueryKeys.detail(datasetId) });
      options?.onSuccess?.();
    },
    onError: options?.onError,
  });
}

/** Hook to validate a dataset */
export function useValidateDataset(options?: { onSuccess?: (data: DatasetValidationResult) => void }) {
  return useMutation({
    mutationFn: async (datasetId: string) => {
      return await DatasetService.validateDataset(datasetId);
    },
    onSuccess: (data) => {
      options?.onSuccess?.(data);
    },
  });
}

/** Hook to export a dataset */
export function useExportDataset() {
  return useMutation({
    mutationFn: async ({ datasetId, format }: { datasetId: string; format: "json" | "jsonl" | "yaml" }) => {
      return await DatasetService.exportDataset(datasetId, format);
    },
  });
}
