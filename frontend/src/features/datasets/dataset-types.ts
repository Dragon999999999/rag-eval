/**
 * Dataset domain types and data contracts.
 *
 * Based on canonical backend Benchmark/BenchmarkCase models.
 */

/** Answerability enum - canonical backend values */
export type Answerability = "ANSWERABLE" | "UNANSWERABLE" | "AMBIGUOUS" | "UNKNOWN";

/** Conversation message role */
export type MessageRole = "user" | "assistant" | "system";

/** Single message in conversation history */
export interface Message {
  role: MessageRole;
  content: string;
}

/** Gold evidence span - stable source location */
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

/** Benchmark case - single evaluation instance */
export interface BenchmarkCase {
  case_id: string;
  query: string;
  history: Message[];
  reference_answer?: string | null;
  gold_evidence: EvidenceSpan[];
  answerability?: Answerability | null;
  tags: string[];
  difficulty?: string | null;
  language?: string | null;
  metadata?: Record<string, unknown>;
}

/** Dataset/benchmark manifest metadata */
export interface BenchmarkManifest {
  benchmark_id: string;
  name: string;
  version: string;
  schema_version: string;
  content_hash?: string | null;
  case_count?: number | null;
  corpus_id?: string | null;
  created_at?: string | null;
  source?: string | null;
  tags: string[];
  metadata?: Record<string, unknown>;
}

/** Dataset info for listing - from backend API */
export interface DatasetInfo {
  dataset_id: string;
  name: string;
  version: string;
  case_count: number | null;
  manifest_hash?: string | null;
  schema_version: string;
  source?: string | null;
  tags: string[];
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/** Dataset creation payload */
export interface DatasetCreate {
  name: string;
  version: string;
  schema_version?: string;
  source?: string | null;
  tags?: string[];
  metadata?: Record<string, unknown>;
}

/** Dataset update payload */
export interface DatasetUpdate {
  name?: string;
  version?: string;
  metadata?: Record<string, unknown> | null;
}

/** Case creation payload */
export interface CaseCreate {
  case_id?: string;
  query: string;
  history?: Message[];
  reference_answer?: string | null;
  gold_evidence?: EvidenceSpan[];
  answerability?: Answerability | null;
  tags?: string[];
  difficulty?: string | null;
  language?: string | null;
  metadata?: Record<string, unknown>;
}

/** Case update payload */
export interface CaseUpdate {
  query?: string;
  history?: Message[];
  reference_answer?: string | null;
  gold_evidence?: EvidenceSpan[];
  answerability?: Answerability | null;
  tags?: string[];
  difficulty?: string | null;
  language?: string | null;
  metadata?: Record<string, unknown>;
}

/** Case summary for listing */
export interface CaseSummary {
  case_id: string;
  query: string;
  answerability: Answerability | null;
  tags: string[];
  metadata?: Record<string, unknown>;
}

/** Validation error for a case */
export interface CaseValidationError {
  case_id: string;
  field?: string;
  message: string;
}

/** Dataset validation result */
export interface DatasetValidationResult {
  dataset_id: string;
  valid: boolean;
  total_cases: number;
  valid_cases: number;
  invalid_cases: number;
  errors: CaseValidationError[];
}

/** Import format */
export type ImportFormat = "json" | "jsonl" | "yaml";

/** Import result */
export interface ImportResult {
  dataset_id: string;
  format: ImportFormat;
  total_cases: number;
  valid_cases: number;
  invalid_cases: number;
  errors: CaseValidationError[];
}

/** Export format */
export type ExportFormat = "json" | "jsonl" | "yaml";

/** Pagination parameters */
export interface PaginationParams {
  limit?: number;
  offset?: number;
  page?: number;
}

/** Paginated response */
export interface PaginatedCases {
  cases: CaseSummary[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}
