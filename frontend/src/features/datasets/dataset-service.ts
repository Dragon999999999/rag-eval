/**
 * Dataset service API client.
 *
 * Centralized service for dataset and case CRUD operations.
 * Uses mock implementation - replace with real HTTP calls when backend is available.
 */
import type {
  DatasetInfo,
  DatasetCreate,
  DatasetUpdate,
  BenchmarkCase,
  CaseCreate,
  CaseUpdate,
  PaginatedCases,
  DatasetValidationResult,
  ImportResult,
  CaseValidationError,
  ImportFormat,
  ExportFormat,
} from "./dataset-types";

const MOCK_DELAY_MS = 400;

/** Error with code and status properties */
interface ServiceError extends Error {
  code?: string;
  status?: number;
}

/** In-memory mock dataset store */
const mockDatasets = new Map<string, DatasetInfo>();
const mockCases = new Map<string, Map<string, BenchmarkCase>>(); // datasetId -> caseId -> case

/** Initialize with mock data */
function initializeMockData() {
  if (mockDatasets.size > 0) return;

  // QKD Benchmark dataset
  const qkdDataset: DatasetInfo = {
    dataset_id: "dataset-qkd-001",
    name: "QKD Grounding Benchmark",
    version: "1.0",
    case_count: 250,
    manifest_hash: "sha256:abc123...",
    schema_version: "1.0",
    source: "QKD Research Corp",
    tags: ["qkd", "factual", "citation"],
    metadata: { domain: "quantum-computing" },
    created_at: new Date(Date.now() - 86400000 * 30).toISOString(), // 30 days ago
    updated_at: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
  };

  mockDatasets.set(qkdDataset.dataset_id, qkdDataset);

  // Initialize cases for this dataset
  const qkdCases = new Map<string, BenchmarkCase>();
  
  // Add sample cases
  for (let i = 1; i <= 10; i++) {
    const caseId = `case-${String(i).padStart(3, "0")}`;
    qkdCases.set(caseId, {
      case_id: caseId,
      query: `What is quantum key distribution case ${String(i)}?`,
      history: i % 3 === 0 ? [{ role: "user" as const, content: "Explain QKD" }] : [],
      reference_answer: i % 2 === 0 ? `Reference answer for case ${String(i)}` : null,
      gold_evidence: i % 2 === 0 ? [{
        evidence_id: `ev-${String(i)}`,
        document_id: "qkd-paper.pdf",
        page: 14,
        start_char: 100,
        end_char: 250,
        text: "Quantum key distribution uses quantum mechanics...",
      }] : [],
      answerability: i % 5 === 0 ? "UNANSWERABLE" : "ANSWERABLE",
      tags: i % 3 === 0 ? ["advanced"] : ["basic"],
      difficulty: i % 4 === 0 ? "hard" : "easy",
      language: "en",
      metadata: {},
    });
  }

  mockCases.set(qkdDataset.dataset_id, qkdCases);

  // Citation benchmark dataset
  const citationDataset: DatasetInfo = {
    dataset_id: "dataset-citation-002",
    name: "Citation Benchmark",
    version: "2.1",
    case_count: 100,
    manifest_hash: "sha256:def456...",
    schema_version: "1.0",
    source: "Internal",
    tags: ["citation", "legal"],
    metadata: { domain: "legal" },
    created_at: new Date(Date.now() - 86400000 * 60).toISOString(),
    updated_at: new Date(Date.now() - 86400000 * 7).toISOString(),
  };

  mockDatasets.set(citationDataset.dataset_id, citationDataset);
  mockCases.set(citationDataset.dataset_id, new Map());
}

export const DatasetService = {
  /** List all datasets */
  async listDatasets(): Promise<DatasetInfo[]> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));
    return Array.from(mockDatasets.values()).sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    );
  },

  /** Get a single dataset */
  async getDataset(datasetId: string): Promise<DatasetInfo> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));
    const dataset = mockDatasets.get(datasetId);
    if (!dataset) {
      const error = new Error(`Dataset not found: ${datasetId}`) as ServiceError;
      error.code = "DATASET_NOT_FOUND";
      error.status = 404;
      throw error;
    }
    return dataset;
  },

  /** Create a new dataset */
  async createDataset(data: DatasetCreate): Promise<DatasetInfo> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const datasetId = `dataset-${String(Date.now())}-${Math.random().toString(36).slice(2, 8)}`;
    const now = new Date().toISOString();

    const dataset: DatasetInfo = {
      dataset_id: datasetId,
      name: data.name,
      version: data.version,
      case_count: 0,
      schema_version: data.schema_version ?? "1.0",
      source: data.source ?? null,
      tags: data.tags ?? [],
      metadata: data.metadata,
      created_at: now,
      updated_at: now,
    };

    mockDatasets.set(datasetId, dataset);
    mockCases.set(datasetId, new Map());
    return dataset;
  },

  /** Update dataset metadata */
  async updateDataset(datasetId: string, data: DatasetUpdate): Promise<DatasetInfo> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const existing = mockDatasets.get(datasetId);
    if (!existing) {
      const error = new Error(`Dataset not found: ${datasetId}`) as ServiceError;
      error.code = "DATASET_NOT_FOUND";
      error.status = 404;
      throw error;
    }

    const updated: DatasetInfo = {
      ...existing,
      name: data.name ?? existing.name,
      version: data.version ?? existing.version,
      metadata: data.metadata ?? existing.metadata,
      updated_at: new Date().toISOString(),
    };

    mockDatasets.set(datasetId, updated);
    return updated;
  },

  /** Delete a dataset */
  async deleteDataset(datasetId: string): Promise<void> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    if (!mockDatasets.has(datasetId)) {
      const error = new Error(`Dataset not found: ${datasetId}`) as ServiceError;
      error.code = "DATASET_NOT_FOUND";
      error.status = 404;
      throw error;
    }

    mockDatasets.delete(datasetId);
    mockCases.delete(datasetId);
  },

  /** List cases with pagination */
  async listCases(
    datasetId: string,
    params?: { limit?: number; offset?: number; search?: string; tag?: string }
  ): Promise<PaginatedCases> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const cases = mockCases.get(datasetId);
    if (!cases) {
      const error = new Error(`Dataset not found: ${datasetId}`) as ServiceError;
      error.code = "DATASET_NOT_FOUND";
      error.status = 404;
      throw error;
    }

    let allCases = Array.from(cases.values());

    // Apply search filter
    if (params?.search) {
      const search = params.search.toLowerCase();
      allCases = allCases.filter((c) => c.query.toLowerCase().includes(search));
    }

    // Apply tag filter
    if (params?.tag) {
      const tag = params.tag;
      allCases = allCases.filter((c) => c.tags.includes(tag));
    }

    const total = allCases.length;
    const limit = params?.limit ?? 20;
    const offset = params?.offset ?? 0;

    const paginatedCases = allCases.slice(offset, offset + limit);

    return {
      cases: paginatedCases.map((c) => ({
        case_id: c.case_id,
        query: c.query,
        answerability: c.answerability ?? null,
        tags: c.tags,
        metadata: c.metadata,
      })),
      total,
      limit,
      offset,
      has_more: offset + limit < total,
    };
  },

  /** Get a single case */
  async getCase(datasetId: string, caseId: string): Promise<BenchmarkCase> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const cases = mockCases.get(datasetId);
    if (!cases) {
      const error = new Error(`Dataset not found: ${datasetId}`) as ServiceError;
      error.code = "DATASET_NOT_FOUND";
      error.status = 404;
      throw error;
    }

    const caseData = cases.get(caseId);
    if (!caseData) {
      const error = new Error(`Case not found: ${caseId}`) as ServiceError;
      error.code = "CASE_NOT_FOUND";
      error.status = 404;
      throw error;
    }

    return caseData;
  },

  /** Create a new case */
  async createCase(datasetId: string, data: CaseCreate): Promise<BenchmarkCase> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const cases = mockCases.get(datasetId);
    if (!cases) {
      const error = new Error(`Dataset not found: ${datasetId}`) as ServiceError;
      error.code = "DATASET_NOT_FOUND";
      error.status = 404;
      throw error;
    }

    const caseId = data.case_id ?? `case-${String(Date.now())}-${Math.random().toString(36).slice(2, 8)}`;
    
    const caseData: BenchmarkCase = {
      case_id: caseId,
      query: data.query,
      history: data.history ?? [],
      reference_answer: data.reference_answer ?? null,
      gold_evidence: data.gold_evidence ?? [],
      answerability: data.answerability ?? null,
      tags: data.tags ?? [],
      difficulty: data.difficulty ?? null,
      language: data.language ?? null,
      metadata: data.metadata ?? {},
    };

    cases.set(caseId, caseData);
    
    // Update dataset case count
    const dataset = mockDatasets.get(datasetId);
    if (dataset) {
      dataset.case_count = (dataset.case_count ?? 0) + 1;
      dataset.updated_at = new Date().toISOString();
    }

    return caseData;
  },

  /** Update a case */
  async updateCase(datasetId: string, caseId: string, data: CaseUpdate): Promise<BenchmarkCase> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const cases = mockCases.get(datasetId);
    if (!cases) {
      const error = new Error(`Dataset not found: ${datasetId}`) as ServiceError;
      error.code = "DATASET_NOT_FOUND";
      error.status = 404;
      throw error;
    }

    const existing = cases.get(caseId);
    if (!existing) {
      const error = new Error(`Case not found: ${caseId}`) as ServiceError;
      error.code = "CASE_NOT_FOUND";
      error.status = 404;
      throw error;
    }

    const updated: BenchmarkCase = {
      ...existing,
      query: data.query ?? existing.query,
      history: data.history ?? existing.history,
      reference_answer: data.reference_answer ?? existing.reference_answer,
      gold_evidence: data.gold_evidence ?? existing.gold_evidence,
      answerability: data.answerability ?? existing.answerability,
      tags: data.tags ?? existing.tags,
      difficulty: data.difficulty ?? existing.difficulty,
      language: data.language ?? existing.language,
      metadata: data.metadata ?? existing.metadata,
    };

    cases.set(caseId, updated);
    return updated;
  },

  /** Delete a case */
  async deleteCase(datasetId: string, caseId: string): Promise<void> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const cases = mockCases.get(datasetId);
    if (!cases) {
      const error = new Error(`Dataset not found: ${datasetId}`) as ServiceError;
      error.code = "DATASET_NOT_FOUND";
      error.status = 404;
      throw error;
    }

    if (!cases.has(caseId)) {
      const error = new Error(`Case not found: ${caseId}`) as ServiceError;
      error.code = "CASE_NOT_FOUND";
      error.status = 404;
      throw error;
    }

    cases.delete(caseId);
    
    // Update dataset case count
    const dataset = mockDatasets.get(datasetId);
    if (dataset) {
      dataset.case_count = Math.max(0, (dataset.case_count ?? 1) - 1);
      dataset.updated_at = new Date().toISOString();
    }
  },

  /** Validate dataset */
  async validateDataset(datasetId: string): Promise<DatasetValidationResult> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS + 500));

    const cases = mockCases.get(datasetId);
    if (!cases) {
      const error = new Error(`Dataset not found: ${datasetId}`) as ServiceError;
      error.code = "DATASET_NOT_FOUND";
      error.status = 404;
      throw error;
    }

    const errors: CaseValidationError[] = [];
    let validCases = 0;

    cases.forEach((caseData, caseId) => {
      // Simple validation: query must exist
      if (!caseData.query || caseData.query.trim().length === 0) {
        errors.push({
          case_id: caseId,
          field: "query",
          message: "Query is required",
        });
      } else {
        validCases++;
      }
    });

    return {
      dataset_id: datasetId,
      valid: errors.length === 0,
      total_cases: cases.size,
      valid_cases: validCases,
      invalid_cases: errors.length,
      errors,
    };
  },

  /** Import dataset from file */
  async importDataset(
    _file: File,
    _format?: ImportFormat
  ): Promise<ImportResult> {
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS + 1000));

    // Mock import - in real impl would upload file to backend
    const datasetId = `dataset-import-${String(Date.now())}`;
    const totalCases = Math.floor(Math.random() * 100) + 50;
    const invalidCases = Math.floor(Math.random() * 5);

    return {
      dataset_id: datasetId,
      format: _format ?? "json",
      total_cases: totalCases,
      valid_cases: totalCases - invalidCases,
      invalid_cases: invalidCases,
      errors: invalidCases > 0 ? [{
        case_id: "case-001",
        field: "query",
        message: "Query is required",
      }] : [],
    };
  },

  /** Export dataset */
  async exportDataset(datasetId: string, _format: ExportFormat): Promise<Blob> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const dataset = mockDatasets.get(datasetId);
    if (!dataset) {
      const error = new Error(`Dataset not found: ${datasetId}`) as ServiceError;
      error.code = "DATASET_NOT_FOUND";
      error.status = 404;
      throw error;
    }

    // Mock export - in real impl would download from backend
    const exportData = {
      manifest: dataset,
      cases: Array.from(mockCases.get(datasetId)?.values() ?? []),
    };

    return new Blob([JSON.stringify(exportData, null, 2)], {
      type: _format === "json" ? "application/json" : "application/jsonl",
    });
  },
};
