/**
 * Target domain types and data contracts.
 *
 * These types represent the frontend's view of target data,
 * based on the backend Target Protocol v1 specification.
 */

/** Target adapter type - must match backend support */
export type TargetAdapterType = "http" | "python";

/** Corpus mode for target configuration */
export type CorpusMode = "DOCUMENTS" | "CHUNKS" | "EXTERNAL";

/** Target connection status derived from backend state */
export type TargetConnectionStatus =
  | "connected"
  | "disconnected"
  | "unknown"
  | "testing"
  | "configuration-error";

/** Target identity information */
export interface Target {
  targetId: string;
  name: string;
  version: string | null;
  implementation: string | null;
  adapter: TargetAdapterType;
  base_url: string | null;
  python_target: string | null;
  authentication_env: string | null;
  corpus_mode: CorpusMode;
  parameters: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at: string; // ISO timestamp
  updated_at: string; // ISO timestamp
}

/** Target creation payload */
export interface TargetCreate {
  name: string;
  version?: string | null;
  implementation?: string | null;
  adapter: TargetAdapterType;
  base_url?: string | null;
  python_target?: string | null;
  authentication_env?: string | null;
  corpus_mode: CorpusMode;
  parameters?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

/** Target update payload */
export interface TargetUpdate {
  name?: string | null;
  version?: string | null;
  implementation?: string | null;
  parameters?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
}

/** Target capabilities as advertised by the backend */
export interface TargetCapabilities {
  target_id: string;
  capabilities: {
    protocol_version?: string;
    query?: boolean;
    streaming?: boolean;
    conversation_history?: boolean;
    retrieval?: boolean;
    retrieval_stages?: boolean;
    document_ingestion?: boolean;
    chunk_ingestion?: boolean;
    context_injection?: boolean;
    citations?: boolean;
    confidence?: boolean;
    target_trace?: boolean;
    effective_configuration?: boolean;
    idempotency?: boolean;
    request_recovery?: boolean;
    usage?: {
      tokens?: boolean;
      cost?: boolean;
      cpu?: boolean;
      ram?: boolean;
      gpu?: boolean;
      vram?: boolean;
    };
    retrieval_metadata?: {
      rank?: boolean;
      score?: boolean;
      document_id?: boolean;
      chunk_id?: boolean;
      page?: boolean;
      character_span?: boolean;
    };
    limits?: Record<string, number>;
    idempotency_retention_seconds?: number | null;
    metadata?: Record<string, unknown>;
  };
  discovered_at: string; // ISO timestamp
}

/** Connection test result from backend */
export interface TargetConnectionTestResult {
  success: boolean;
  target_id: string;
  response_time_ms?: number;
  error?: string;
  error_category?: string;
  error_code?: string;
  http_status?: number;
  details?: Record<string, unknown>;
  tested_at: string; // ISO timestamp
}

/** Authentication configuration for targets */
export interface TargetAuthConfig {
  type: "none" | "bearer" | "api-key";
  bearer_token?: string;
  api_key?: string;
  api_key_header?: string;
  authentication_env?: string | null;
}

/** Adapter-specific configuration */
export interface HttpAdapterConfig {
  base_url: string;
  authentication: TargetAuthConfig;
}

export interface PythonAdapterConfig {
  python_target: string; // module:Symbol format
}

/** Form state for target creation/editing */
export interface TargetFormState {
  name: string;
  description?: string;
  adapter: TargetAdapterType;
  
  // HTTP adapter fields
  base_url?: string;
  auth_type?: "none" | "bearer" | "api-key";
  bearer_token?: string;
  api_key?: string;
  api_key_header?: string;
  
  // Python adapter fields
  python_target?: string;
  
  // Common fields
  corpus_mode: CorpusMode;
  version?: string;
  implementation?: string;
  parameters?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}
