/** API response and request types for evaluator-managed targets. */

export type TargetConfigurationStatus =
  "empty" | "configured" | "invalid" | (string & {});
export type TargetConnectionStatus =
  "not_tested" | "connected" | "unverified" | "disconnected" | (string & {});

/** The backend's evaluator-owned target summary. */
export interface TargetSummary {
  target_id: string;
  name: string;
  adapter_type: string | null;
  configuration_status: TargetConfigurationStatus;
  connection_status: TargetConnectionStatus;
  current_config_version: number | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

/** Full target state returned by the backend. */
export interface Target extends Omit<TargetSummary, "connection_status"> {
  /** Detail responses embed connection state rather than repeating its status. */
  connection_status?: TargetConnectionStatus;
  connection: TargetConnection | null;
  capabilities: TargetCapabilitiesPayload | null;
  metadata: Record<string, unknown>;
}

export interface TargetCreate {
  name: string;
  metadata?: Record<string, unknown>;
}

export interface TargetUpdate {
  name?: string;
  metadata?: Record<string, unknown>;
  enabled?: boolean;
}

export interface TargetAdapterInfo {
  type: string;
  version: string | null;
  description: string | null;
  supports_overrides: boolean;
  supports_full_protocol: boolean;
  defaults: Record<string, unknown>;
}

export interface TargetConnection {
  status: TargetConnectionStatus;
  checked_at: string | null;
  last_successful_at: string | null;
  health: Record<string, unknown> | null;
  error: Record<string, unknown> | null;
}

export interface TargetCapabilitiesPayload {
  target_id?: string;
  capabilities: Record<string, unknown>;
}

export type TargetConnectionInfo = TargetConnection;

export interface TargetConfigVersionInfo {
  config_version_id: string;
  version: number;
  schema_version: string;
  source_artifact_id: string;
  config_hash: string;
  created_at: string;
}

export interface TargetConfigVersionDetail extends TargetConfigVersionInfo {
  target_id: string;
  yaml: string;
}

export interface TargetConfigurationResponse {
  target_id: string;
  version: number;
  yaml: string;
}

export interface TargetAdapterSourceInfo {
  target_id: string;
  filename: string;
  artifact_id: string;
  content_hash: string | null;
  created_at: string | null;
}

export interface TargetCapabilitiesInfo {
  target_id: string;
  capabilities: Record<string, unknown>;
}

/** Values used by the structured editor before serialization to target.yaml. */
export interface TargetConfigurationDraft {
  adapter: string;
  base_url: string;
  timeout_seconds: string;
  verify_tls: boolean;
  auth_type: string;
  bearer_token: string;
  api_key: string;
  api_key_header: string;
  model: string;
  endpoint: string;
  protocol_json: string;
  overrides_json: string;
  parameters_json: string;
  metadata_json: string;
  /** SecretRef values from the sanitized configuration, never rendered as plaintext. */
  existing_auth: Record<string, unknown>;
}
