/** HTTP client for the canonical benchmark and content resource APIs. */
import { apiRequest } from "@/lib/api/client";
import type {
  BenchmarkCase,
  BenchmarkCreate,
  BenchmarkDocument,
  BenchmarkFileCreate,
  BenchmarkInfo,
  BenchmarkChunk,
  CorpusMode,
} from "./dataset-types";

type ApiEnvelope<T> = T | { data: T } | { items: T };

function unwrap<T>(payload: ApiEnvelope<T>): T {
  if (typeof payload === "object" && payload !== null) {
    if ("data" in payload) return payload.data;
    if ("items" in payload) return payload.items;
  }
  return payload;
}

function filesFormData(files: File[]): FormData {
  const form = new FormData();
  files.forEach((file) => {
    form.append("files", file, file.name);
  });
  return form;
}

function createFormData(data: BenchmarkFileCreate): FormData {
  const form = new FormData();
  form.append("name", data.name);
  form.append("version", data.version ?? "1");
  form.append("corpus_mode", data.corpus_mode ?? "DOCUMENTS");
  data.cases?.forEach((file) => {
    form.append("cases", file, file.name);
  });
  data.documents?.forEach((file) => {
    form.append("documents", file, file.name);
  });
  data.chunks?.forEach((file) => {
    form.append("chunks", file, file.name);
  });
  return form;
}

export const BenchmarkService = {
  async listBenchmarks(): Promise<BenchmarkInfo[]> {
    return unwrap(await apiRequest<ApiEnvelope<BenchmarkInfo[]>>("/api/v1/benchmarks"));
  },

  async getBenchmark(benchmarkId: string): Promise<BenchmarkInfo> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkInfo>>(
        `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}`
      )
    );
  },

  async createBenchmark(data: BenchmarkCreate): Promise<BenchmarkInfo> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkInfo>>("/api/v1/benchmarks", {
        method: "POST",
        body: {
          name: data.name,
          version: data.version ?? "1",
          corpus_mode: data.corpus_mode ?? "DOCUMENTS",
        },
      })
    );
  },

  async createBenchmarkFromFiles(data: BenchmarkFileCreate): Promise<BenchmarkInfo> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkInfo>>("/api/v1/benchmarks/from-files", {
        method: "POST",
        body: createFormData(data),
      })
    );
  },

  async deleteBenchmark(benchmarkId: string): Promise<void> {
    await apiRequest<undefined>(
      `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}`,
      {
        method: "DELETE",
      }
    );
  },

  async changeCorpusMode(
    benchmarkId: string,
    corpusMode: CorpusMode
  ): Promise<BenchmarkInfo> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkInfo>>(
        `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/corpus-mode`,
        { method: "PUT", body: { corpus_mode: corpusMode } }
      )
    );
  },

  async listCases(benchmarkId: string): Promise<BenchmarkCase[]> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkCase[]>>(
        `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/cases`
      )
    );
  },

  async createCase(benchmarkId: string, data: BenchmarkCase): Promise<BenchmarkCase> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkCase>>(
        `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/cases`,
        { method: "POST", body: data }
      )
    );
  },

  async importCases(benchmarkId: string, files: File[]): Promise<BenchmarkInfo> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkInfo>>(
        `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/cases/import`,
        { method: "POST", body: filesFormData(files) }
      )
    );
  },

  /** Compatibility name for callers that still use the pre-import API. */
  addCases(benchmarkId: string, files: File[]) {
    return this.importCases(benchmarkId, files);
  },

  async getCase(benchmarkId: string, caseId: string): Promise<BenchmarkCase> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkCase>>(
        `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/cases/${encodeURIComponent(caseId)}`
      )
    );
  },

  updateCase(
    _benchmarkId: string,
    _caseId: string,
    _data: Partial<BenchmarkCase>
  ): Promise<BenchmarkCase> {
    return Promise.reject(
      new Error("Case editing is not supported by the backend yet")
    );
  },

  async deleteCase(benchmarkId: string, caseId: string): Promise<void> {
    await apiRequest<undefined>(
      `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/cases/${encodeURIComponent(caseId)}`,
      { method: "DELETE" }
    );
  },

  async listDocuments(benchmarkId: string): Promise<BenchmarkDocument[]> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkDocument[]>>(
        `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/documents`
      )
    );
  },

  async uploadDocuments(benchmarkId: string, files: File[]): Promise<BenchmarkInfo> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkInfo>>(
        `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/documents`,
        { method: "POST", body: filesFormData(files) }
      )
    );
  },

  /** Compatibility name for callers that still use the pre-upload API. */
  addDocuments(benchmarkId: string, files: File[]) {
    return this.uploadDocuments(benchmarkId, files);
  },

  async getDocument(
    benchmarkId: string,
    documentId: string
  ): Promise<BenchmarkDocument> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkDocument>>(
        `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/documents/${encodeURIComponent(documentId)}`
      )
    );
  },

  async deleteDocument(benchmarkId: string, documentId: string): Promise<void> {
    await apiRequest<undefined>(
      `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/documents/${encodeURIComponent(documentId)}`,
      { method: "DELETE" }
    );
  },

  async listChunks(benchmarkId: string): Promise<BenchmarkChunk[]> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkChunk[]>>(
        `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/chunks`
      )
    );
  },

  async createChunk(
    benchmarkId: string,
    data: BenchmarkChunk
  ): Promise<BenchmarkChunk> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkChunk>>(
        `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/chunks`,
        { method: "POST", body: data }
      )
    );
  },

  async importChunks(benchmarkId: string, files: File[]): Promise<BenchmarkInfo> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkInfo>>(
        `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/chunks/import`,
        { method: "POST", body: filesFormData(files) }
      )
    );
  },

  /** Compatibility name for callers that still use the pre-import API. */
  addChunks(benchmarkId: string, files: File[]) {
    return this.importChunks(benchmarkId, files);
  },

  async getChunk(benchmarkId: string, chunkId: string): Promise<BenchmarkChunk> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkChunk>>(
        `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/chunks/${encodeURIComponent(chunkId)}`
      )
    );
  },

  async deleteChunk(benchmarkId: string, chunkId: string): Promise<void> {
    await apiRequest<undefined>(
      `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/chunks/${encodeURIComponent(chunkId)}`,
      { method: "DELETE" }
    );
  },

  // Legacy names retained for consumers not yet migrated to benchmark naming.
  listDatasets() {
    return this.listBenchmarks();
  },
  getDataset(benchmarkId: string) {
    return this.getBenchmark(benchmarkId);
  },
  createDataset(data: BenchmarkCreate) {
    return this.createBenchmark(data);
  },
};

export const DatasetService = BenchmarkService;
