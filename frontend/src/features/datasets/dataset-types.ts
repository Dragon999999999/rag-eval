/**
 * Frontend contracts for the benchmark API.
 *
 * Benchmarks are the primary resource. The `Dataset*` names at the bottom of
 * this module are kept as source-compatible aliases for the test builder while
 * the rest of the application moves away from the old dataset terminology.
 */

export type CorpusMode = "DOCUMENTS" | "CHUNKS" | "EXTERNAL";
export type Answerability = "ANSWERABLE" | "UNANSWERABLE" | "AMBIGUOUS" | "UNKNOWN";
export type MessageRole = "user" | "assistant" | "system";

export interface Message {
  role: MessageRole;
  content: string;
}

export interface EvidenceSpan {
  evidence_id: string;
  document_id: string;
  page?: number;
  start_char?: number;
  end_char?: number;
  text?: string;
  relevance?: number;
  metadata?: Record<string, unknown>;
}

export interface BenchmarkCase {
  case_id: string;
  query: string;
  history?: Message[];
  reference_answer?: string | null;
  gold_evidence?: EvidenceSpan[];
  answerability?: string | null;
  tags: string[];
  difficulty?: string | null;
  language?: string | null;
  metadata?: Record<string, unknown>;
}

export interface BenchmarkDocument {
  document_id: string;
  filename?: string | null;
  mime_type?: string | null;
  sha256?: string | null;
  size_bytes?: number | null;
  metadata?: Record<string, unknown>;
}

export interface BenchmarkChunk {
  chunk_id: string;
  document_id: string;
  text: string;
  location?: Record<string, unknown> | null;
  metadata?: Record<string, unknown>;
}

/** Metadata and counts returned by benchmark list/detail endpoints. */
export interface BenchmarkInfo {
  benchmark_id: string;
  name: string;
  version: string;
  schema_version?: string;
  corpus_mode: CorpusMode;
  content_hash?: string | null;
  corpus_id?: string | null;
  source?: string | null;
  tags: string[];
  metadata: Record<string, unknown>;
  case_count: number;
  document_count: number;
  chunk_count: number;
  is_complete?: boolean;
  available_corpus_modes?: CorpusMode[];
  created_at?: string | null;
  updated_at?: string | null;
  /** Detail responses include the complete records when available. */
  cases?: BenchmarkCase[];
  documents?: BenchmarkDocument[];
  chunks?: BenchmarkChunk[];
}

export type BenchmarkDetail = BenchmarkInfo & {
  cases: BenchmarkCase[];
  documents: BenchmarkDocument[];
  chunks: BenchmarkChunk[];
};

export interface BenchmarkCreate {
  name: string;
  version?: string;
  corpus_mode?: CorpusMode;
}

export interface BenchmarkFileCreate {
  name: string;
  version?: string;
  corpus_mode?: CorpusMode;
  cases?: File[];
  documents?: File[];
  chunks?: File[];
}

export interface CaseSummary {
  case_id: string;
  query: string;
  answerability: string | null;
  tags: string[];
  metadata?: Record<string, unknown>;
}

export interface PaginatedCases {
  cases: CaseSummary[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

// Compatibility types used by older consumers. New UI code should use the
// benchmark names above.
export type DatasetInfo = BenchmarkInfo;
export type DatasetCreate = BenchmarkCreate;
export type DatasetUpdate = Partial<BenchmarkCreate>;
export type BenchmarkManifest = BenchmarkInfo;
export type CaseCreate = Partial<BenchmarkCase> & Pick<BenchmarkCase, "query">;
export type CaseUpdate = Partial<BenchmarkCase>;

export interface CaseValidationError {
  case_id: string;
  field?: string;
  message: string;
}

export interface DatasetValidationResult {
  benchmark_id: string;
  valid: boolean;
  total_cases: number;
  valid_cases: number;
  invalid_cases: number;
  errors: CaseValidationError[];
}

export interface ImportResult {
  benchmark_id: string;
  format: ImportFormat;
  total_cases: number;
  valid_cases: number;
  invalid_cases: number;
  errors: CaseValidationError[];
}

export type ImportFormat = "json" | "jsonl" | "yaml";
export type ExportFormat = "json" | "jsonl" | "yaml";
