/** HTTP client for the canonical benchmark API. */
import { apiRequest } from "@/lib/api/client";
import type {
  BenchmarkCase,
  BenchmarkCreate,
  BenchmarkDetail,
  BenchmarkFileCreate,
  BenchmarkInfo,
  CaseSummary,
  PaginatedCases,
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
  if (data.version) form.append("version", data.version);
  if (data.corpus_mode) form.append("corpus_mode", data.corpus_mode);
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

function detailWithDefaults(benchmark: BenchmarkInfo): BenchmarkDetail {
  return {
    ...benchmark,
    cases: benchmark.cases ?? [],
    documents: benchmark.documents ?? [],
    chunks: benchmark.chunks ?? [],
  };
}

export const BenchmarkService = {
  /** Load all benchmark summaries from the API. */
  async listBenchmarks(): Promise<BenchmarkInfo[]> {
    const payload =
      await apiRequest<ApiEnvelope<BenchmarkInfo[]>>("/api/v1/benchmarks");
    return unwrap(payload);
  },

  /** Load one complete benchmark and its attached records. */
  async getBenchmark(benchmarkId: string): Promise<BenchmarkDetail> {
    const payload = await apiRequest<ApiEnvelope<BenchmarkInfo>>(
      `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}`
    );
    return detailWithDefaults(unwrap(payload));
  },

  /** Create an empty benchmark using the JSON API. */
  async createBenchmark(data: BenchmarkCreate): Promise<BenchmarkInfo> {
    const payload = await apiRequest<ApiEnvelope<BenchmarkInfo>>("/api/v1/benchmarks", {
      method: "POST",
      body: {
        name: data.name,
        version: data.version ?? "1",
        corpus_mode: data.corpus_mode ?? "DOCUMENTS",
      },
    });
    return unwrap(payload);
  },

  /** Create a benchmark and optionally attach multiple uploaded files. */
  async createBenchmarkFromFiles(data: BenchmarkFileCreate): Promise<BenchmarkInfo> {
    const payload = await apiRequest<ApiEnvelope<BenchmarkInfo>>(
      "/api/v1/benchmarks/from-files",
      { method: "POST", body: createFormData(data) }
    );
    return unwrap(payload);
  },

  /** Upload one or more JSON/JSONL case files to an existing benchmark. */
  async addCases(benchmarkId: string, files: File[]): Promise<BenchmarkInfo> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkInfo>>(
        `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/cases`,
        { method: "POST", body: filesFormData(files) }
      )
    );
  },

  /** Upload source documents to an existing DOCUMENTS benchmark. */
  async addDocuments(benchmarkId: string, files: File[]): Promise<BenchmarkInfo> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkInfo>>(
        `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/documents`,
        { method: "POST", body: filesFormData(files) }
      )
    );
  },

  /** Upload canonical JSON/JSONL chunks to an existing CHUNKS benchmark. */
  async addChunks(benchmarkId: string, files: File[]): Promise<BenchmarkInfo> {
    return unwrap(
      await apiRequest<ApiEnvelope<BenchmarkInfo>>(
        `/api/v1/benchmarks/${encodeURIComponent(benchmarkId)}/chunks`,
        { method: "POST", body: filesFormData(files) }
      )
    );
  },

  // Compatibility aliases for existing feature consumers.
  listDatasets() {
    return this.listBenchmarks();
  },
  getDataset(benchmarkId: string) {
    return this.getBenchmark(benchmarkId);
  },
  createDataset(data: BenchmarkCreate) {
    return this.createBenchmark(data);
  },
  async listCases(
    benchmarkId: string,
    params?: { limit?: number; offset?: number; search?: string; tag?: string }
  ): Promise<PaginatedCases> {
    const detail = await this.getBenchmark(benchmarkId);
    let cases: CaseSummary[] = detail.cases.map((item) => ({
      case_id: item.case_id,
      query: item.query,
      answerability: item.answerability ?? null,
      tags: item.tags,
      metadata: item.metadata,
    }));
    if (params?.search) {
      const search = params.search.toLowerCase();
      cases = cases.filter((item) => item.query.toLowerCase().includes(search));
    }
    if (params?.tag)
      cases = cases.filter((item) => item.tags.includes(params.tag ?? ""));
    const offset = params?.offset ?? 0;
    const limit = params?.limit ?? (cases.length || 20);
    return {
      cases: cases.slice(offset, offset + limit),
      total: cases.length,
      limit,
      offset,
      has_more: offset + limit < cases.length,
    };
  },
  async getCase(benchmarkId: string, caseId: string): Promise<BenchmarkCase> {
    const detail = await this.getBenchmark(benchmarkId);
    const item = detail.cases.find((candidate) => candidate.case_id === caseId);
    if (!item) throw new Error(`Case not found: ${caseId}`);
    return item;
  },
};

/** Backward-compatible export name; all calls use benchmark endpoints. */
export const DatasetService = BenchmarkService;
