/** TanStack Query hooks for benchmark metadata and normalized resources. */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { BenchmarkService } from "./dataset-service";
import type {
  BenchmarkCase,
  BenchmarkChunk,
  BenchmarkCreate,
  BenchmarkDocument,
  BenchmarkFileCreate,
  BenchmarkInfo,
  CorpusMode,
  DatasetValidationResult,
  PaginatedCases,
} from "./dataset-types";

export const benchmarkQueryKeys = {
  all: ["benchmarks"] as const,
  list: () => [...benchmarkQueryKeys.all, "list"] as const,
  detail: (id: string) => [...benchmarkQueryKeys.all, id] as const,
  cases: (id: string) => [...benchmarkQueryKeys.detail(id), "cases"] as const,
  case: (id: string, caseId: string) =>
    [...benchmarkQueryKeys.cases(id), caseId] as const,
  documents: (id: string) => [...benchmarkQueryKeys.detail(id), "documents"] as const,
  document: (id: string, documentId: string) =>
    [...benchmarkQueryKeys.documents(id), documentId] as const,
  chunks: (id: string) => [...benchmarkQueryKeys.detail(id), "chunks"] as const,
  chunk: (id: string, chunkId: string) =>
    [...benchmarkQueryKeys.chunks(id), chunkId] as const,
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
  id: string,
  options?: Omit<UseQueryOptions<BenchmarkInfo>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: benchmarkQueryKeys.detail(id),
    queryFn: () => BenchmarkService.getBenchmark(id),
    enabled: Boolean(id),
    ...options,
  });
}

export function useBenchmarkCases(
  id: string,
  options?: Omit<UseQueryOptions<BenchmarkCase[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: benchmarkQueryKeys.cases(id),
    queryFn: () => BenchmarkService.listCases(id),
    enabled: Boolean(id),
    ...options,
  });
}

export function useBenchmarkCase(
  id: string,
  caseId: string,
  options?: Omit<UseQueryOptions<BenchmarkCase>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: benchmarkQueryKeys.case(id, caseId),
    queryFn: () => BenchmarkService.getCase(id, caseId),
    enabled: Boolean(id && caseId),
    ...options,
  });
}

export function useBenchmarkDocuments(
  id: string,
  options?: Omit<UseQueryOptions<BenchmarkDocument[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: benchmarkQueryKeys.documents(id),
    queryFn: () => BenchmarkService.listDocuments(id),
    enabled: Boolean(id),
    ...options,
  });
}

export function useBenchmarkDocument(
  id: string,
  documentId: string,
  options?: Omit<UseQueryOptions<BenchmarkDocument>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: benchmarkQueryKeys.document(id, documentId),
    queryFn: () => BenchmarkService.getDocument(id, documentId),
    enabled: Boolean(id && documentId),
    ...options,
  });
}

export function useBenchmarkChunks(
  id: string,
  options?: Omit<UseQueryOptions<BenchmarkChunk[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: benchmarkQueryKeys.chunks(id),
    queryFn: () => BenchmarkService.listChunks(id),
    enabled: Boolean(id),
    ...options,
  });
}

export function useBenchmarkChunk(
  id: string,
  chunkId: string,
  options?: Omit<UseQueryOptions<BenchmarkChunk>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: benchmarkQueryKeys.chunk(id, chunkId),
    queryFn: () => BenchmarkService.getChunk(id, chunkId),
    enabled: Boolean(id && chunkId),
    ...options,
  });
}

type MutationOptions<T> = {
  onSuccess?: (data: T) => void;
  onError?: (error: Error) => void;
};

function invalidateBenchmark(
  queryClient: ReturnType<typeof useQueryClient>,
  id: string
) {
  void queryClient.invalidateQueries({ queryKey: benchmarkQueryKeys.detail(id) });
  void queryClient.invalidateQueries({ queryKey: benchmarkQueryKeys.list() });
}

export function useCreateBenchmark(options?: MutationOptions<BenchmarkInfo>) {
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

export function useCreateBenchmarkFromFiles(options?: MutationOptions<BenchmarkInfo>) {
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

export function useDeleteBenchmark(options?: MutationOptions<string>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await BenchmarkService.deleteBenchmark(id);
      return id;
    },
    onSuccess: (id) => {
      queryClient.removeQueries({ queryKey: benchmarkQueryKeys.detail(id) });
      void queryClient.invalidateQueries({ queryKey: benchmarkQueryKeys.list() });
      options?.onSuccess?.(id);
    },
    onError: options?.onError,
  });
}

export function useChangeCorpusMode(
  id: string,
  options?: MutationOptions<BenchmarkInfo>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (mode: CorpusMode) => BenchmarkService.changeCorpusMode(id, mode),
    onSuccess: (data) => {
      invalidateBenchmark(queryClient, id);
      void queryClient.invalidateQueries({ queryKey: benchmarkQueryKeys.cases(id) });
      void queryClient.invalidateQueries({
        queryKey: benchmarkQueryKeys.documents(id),
      });
      void queryClient.invalidateQueries({ queryKey: benchmarkQueryKeys.chunks(id) });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

export function useCreateBenchmarkCase(
  id: string,
  options?: MutationOptions<BenchmarkCase>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: BenchmarkCase) => BenchmarkService.createCase(id, data),
    onSuccess: (data) => {
      invalidateBenchmark(queryClient, id);
      void queryClient.invalidateQueries({ queryKey: benchmarkQueryKeys.cases(id) });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

export function useImportBenchmarkCases(
  id: string,
  options?: MutationOptions<BenchmarkInfo>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (files: File[]) => BenchmarkService.importCases(id, files),
    onSuccess: (data) => {
      invalidateBenchmark(queryClient, id);
      void queryClient.invalidateQueries({ queryKey: benchmarkQueryKeys.cases(id) });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

export function useUpdateBenchmarkCase(
  id: string,
  caseId: string,
  options?: MutationOptions<BenchmarkCase>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<BenchmarkCase>) =>
      BenchmarkService.updateCase(id, caseId, data),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: benchmarkQueryKeys.cases(id) });
      void queryClient.invalidateQueries({
        queryKey: benchmarkQueryKeys.case(id, caseId),
      });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

export function useDeleteBenchmarkCase(id: string, options?: MutationOptions<string>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (caseId: string) => {
      await BenchmarkService.deleteCase(id, caseId);
      return caseId;
    },
    onSuccess: (caseId) => {
      queryClient.removeQueries({ queryKey: benchmarkQueryKeys.case(id, caseId) });
      invalidateBenchmark(queryClient, id);
      void queryClient.invalidateQueries({ queryKey: benchmarkQueryKeys.cases(id) });
      options?.onSuccess?.(caseId);
    },
    onError: options?.onError,
  });
}

export function useUploadBenchmarkDocuments(
  id: string,
  options?: MutationOptions<BenchmarkInfo>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (files: File[]) => BenchmarkService.uploadDocuments(id, files),
    onSuccess: (data) => {
      invalidateBenchmark(queryClient, id);
      void queryClient.invalidateQueries({
        queryKey: benchmarkQueryKeys.documents(id),
      });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

export function useDeleteBenchmarkDocument(
  id: string,
  options?: MutationOptions<string>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (documentId: string) => {
      await BenchmarkService.deleteDocument(id, documentId);
      return documentId;
    },
    onSuccess: (documentId) => {
      queryClient.removeQueries({
        queryKey: benchmarkQueryKeys.document(id, documentId),
      });
      invalidateBenchmark(queryClient, id);
      void queryClient.invalidateQueries({
        queryKey: benchmarkQueryKeys.documents(id),
      });
      options?.onSuccess?.(documentId);
    },
    onError: options?.onError,
  });
}

export function useCreateBenchmarkChunk(
  id: string,
  options?: MutationOptions<BenchmarkChunk>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: BenchmarkChunk) => BenchmarkService.createChunk(id, data),
    onSuccess: (data) => {
      invalidateBenchmark(queryClient, id);
      void queryClient.invalidateQueries({ queryKey: benchmarkQueryKeys.chunks(id) });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

export function useImportBenchmarkChunks(
  id: string,
  options?: MutationOptions<BenchmarkInfo>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (files: File[]) => BenchmarkService.importChunks(id, files),
    onSuccess: (data) => {
      invalidateBenchmark(queryClient, id);
      void queryClient.invalidateQueries({ queryKey: benchmarkQueryKeys.chunks(id) });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

export function useDeleteBenchmarkChunk(id: string, options?: MutationOptions<string>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (chunkId: string) => {
      await BenchmarkService.deleteChunk(id, chunkId);
      return chunkId;
    },
    onSuccess: (chunkId) => {
      queryClient.removeQueries({ queryKey: benchmarkQueryKeys.chunk(id, chunkId) });
      invalidateBenchmark(queryClient, id);
      void queryClient.invalidateQueries({ queryKey: benchmarkQueryKeys.chunks(id) });
      options?.onSuccess?.(chunkId);
    },
    onError: options?.onError,
  });
}

// Compatibility hook names for the test builder and older imports.
export const useDatasetList = useBenchmarkList;
export const useDataset = useBenchmark;
export const useAddBenchmarkCases = useImportBenchmarkCases;
export const useAddBenchmarkDocuments = useUploadBenchmarkDocuments;
export const useAddBenchmarkChunks = useImportBenchmarkChunks;

export function useCaseList(
  id: string,
  params?: { limit?: number; offset?: number; search?: string; tag?: string },
  options?: Omit<UseQueryOptions<PaginatedCases>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: [...benchmarkQueryKeys.cases(id), params] as const,
    queryFn: async () => {
      let cases = await BenchmarkService.listCases(id);
      if (params?.search)
        cases = cases.filter((item) =>
          item.query.toLowerCase().includes(params.search?.toLowerCase() ?? "")
        );
      if (params?.tag)
        cases = cases.filter((item) => item.tags.includes(params.tag ?? ""));
      const offset = params?.offset ?? 0;
      const limit = params?.limit ?? (cases.length || 20);
      return {
        cases: cases.slice(offset, offset + limit).map((item) => ({
          case_id: item.case_id,
          query: item.query,
          answerability: item.answerability ?? null,
          tags: item.tags,
          metadata: item.metadata,
        })),
        total: cases.length,
        limit,
        offset,
        has_more: offset + limit < cases.length,
      };
    },
    enabled: Boolean(id),
    ...options,
  });
}

export const useCase = useBenchmarkCase;

/** Deprecated local validation compatibility hook. */
export function useValidateDataset(options?: {
  onSuccess?: (data: DatasetValidationResult) => void;
}) {
  return useMutation({
    mutationFn: async (id: string): Promise<DatasetValidationResult> => {
      const cases = await BenchmarkService.listCases(id);
      const validCases = cases.filter((item) => item.query.trim().length > 0);
      return {
        benchmark_id: id,
        valid: validCases.length === cases.length,
        total_cases: cases.length,
        valid_cases: validCases.length,
        invalid_cases: cases.length - validCases.length,
        errors: [],
      };
    },
    onSuccess: options?.onSuccess,
  });
}
