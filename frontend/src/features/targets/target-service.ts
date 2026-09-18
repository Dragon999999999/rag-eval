/**
 * Target service API client.
 *
 * Centralized service for target CRUD operations and capability management.
 * Currently uses mock implementation - replace with real HTTP calls when backend is available.
 */
import type {
  Target,
  TargetCreate,
  TargetUpdate,
  TargetCapabilities,
  TargetConnectionTestResult,
} from "./target-types";

/** Simulated delay for mock service. */
const MOCK_DELAY_MS = 400;

/** Error with code and status properties */
interface ServiceError extends Error {
  code?: string;
  status?: number;
  field?: string;
}

/**
 * In-memory mock target store for development.
 */
const mockTargets = new Map<string, Target>();
const mockCapabilities = new Map<string, TargetCapabilities>();

/**
 * Initialize with some mock data for development.
 */
function initializeMockData() {
  if (mockTargets.size > 0) return;

  // Add a sample HTTP target
  const httpTarget: Target = {
    targetId: "target-http-001",
    name: "Grounding RAG Development",
    version: "v3.0",
    implementation: "rag_eval.adapters.http:HttpTargetAdapter",
    adapter: "http",
    base_url: "http://localhost:8000",
    python_target: null,
    authentication_env: "TARGET_API_TOKEN",
    corpus_mode: "DOCUMENTS",
    parameters: {},
    metadata: { environment: "development" },
    created_at: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
    updated_at: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
  };

  mockTargets.set(httpTarget.targetId, httpTarget);

  // Add capabilities for the HTTP target
  mockCapabilities.set(httpTarget.targetId, {
    target_id: httpTarget.targetId,
    capabilities: {
      protocol_version: "1.0",
      query: true,
      streaming: false,
      conversation_history: true,
      retrieval: true,
      retrieval_stages: true,
      document_ingestion: true,
      chunk_ingestion: false,
      context_injection: true,
      citations: true,
      confidence: false,
      target_trace: true,
      effective_configuration: false,
      idempotency: true,
      request_recovery: false,
      usage: {
        tokens: true,
        cost: false,
        cpu: false,
        ram: false,
        gpu: false,
        vram: false,
      },
      retrieval_metadata: {
        rank: true,
        score: true,
        document_id: true,
        chunk_id: false,
        page: false,
        character_span: false,
      },
      limits: {
        max_query_length: 4096,
        max_history_messages: 10,
      },
      idempotency_retention_seconds: 3600,
    },
    discovered_at: new Date(Date.now() - 3600000).toISOString(),
  });

  // Add a sample Python target
  const pythonTarget: Target = {
    targetId: "target-python-002",
    name: "Local Python Target",
    version: "v1.0",
    implementation: "rag_eval.example_target:ExampleTarget",
    adapter: "python",
    base_url: null,
    python_target: "rag_eval.example_target:ExampleTarget",
    authentication_env: null,
    corpus_mode: "EXTERNAL",
    parameters: {},
    metadata: { environment: "local" },
    created_at: new Date(Date.now() - 172800000).toISOString(), // 2 days ago
    updated_at: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
  };

  mockTargets.set(pythonTarget.targetId, pythonTarget);
}

/**
 * Target service API.
 */
export const TargetService = {
  /**
   * List all targets.
   */
  async listTargets(): Promise<Target[]> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));
    return Array.from(mockTargets.values()).sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  },

  /**
   * Get a single target by ID.
   */
  async getTarget(targetId: string): Promise<Target> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));
    const target = mockTargets.get(targetId);
    if (!target) {
      const error = new Error(`Target not found: ${targetId}`);
      (error as ServiceError).code = "TARGET_NOT_FOUND";
      (error as ServiceError).status = 404;
      throw error;
    }
    return target;
  },

  /**
   * Create a new target.
   */
  async createTarget(data: TargetCreate): Promise<Target> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    // Validate adapter-specific fields
    if (data.adapter === "http" && !data.base_url) {
      const error = new Error("Base URL is required for HTTP adapter");
      (error as ServiceError).code = "VALIDATION_ERROR";
      (error as ServiceError).field = "base_url";
      throw error;
    }

    if (data.adapter === "python" && !data.python_target) {
      const error = new Error("Python target is required for Python adapter");
      (error as ServiceError).code = "VALIDATION_ERROR";
      (error as ServiceError).field = "python_target";
      throw error;
    }

    const targetId = `target-${String(Date.now())}-${Math.random().toString(36).slice(2, 8)}`;
    const now = new Date().toISOString();

    const target: Target = {
      targetId,
      name: data.name,
      version: data.version ?? null,
      implementation: data.implementation ?? null,
      adapter: data.adapter,
      base_url: data.base_url ?? null,
      python_target: data.python_target ?? null,
      authentication_env: data.authentication_env ?? null,
      corpus_mode: data.corpus_mode,
      parameters: data.parameters ?? {},
      metadata: data.metadata ?? {},
      created_at: now,
      updated_at: now,
    };

    mockTargets.set(targetId, target);
    return target;
  },

  /**
   * Update an existing target.
   */
  async updateTarget(targetId: string, data: TargetUpdate): Promise<Target> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    const existing = mockTargets.get(targetId);
    if (!existing) {
      const error = new Error(`Target not found: ${targetId}`);
      (error as ServiceError).code = "TARGET_NOT_FOUND";
      (error as ServiceError).status = 404;
      throw error;
    }

    const updated: Target = {
      ...existing,
      name: data.name ?? existing.name,
      version: data.version ?? existing.version,
      implementation: data.implementation ?? existing.implementation,
      parameters: data.parameters ?? existing.parameters,
      metadata: data.metadata ?? existing.metadata,
      updated_at: new Date().toISOString(),
    };

    mockTargets.set(targetId, updated);
    return updated;
  },

  /**
   * Delete a target.
   */
  async deleteTarget(targetId: string): Promise<void> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    if (!mockTargets.has(targetId)) {
      const error = new Error(`Target not found: ${targetId}`);
      (error as ServiceError).code = "TARGET_NOT_FOUND";
      (error as ServiceError).status = 404;
      throw error;
    }

    mockTargets.delete(targetId);
    mockCapabilities.delete(targetId);
  },

  /**
   * Get target capabilities.
   */
  async getCapabilities(targetId: string): Promise<TargetCapabilities> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS));

    if (!mockTargets.has(targetId)) {
      const error = new Error(`Target not found: ${targetId}`);
      (error as ServiceError).code = "TARGET_NOT_FOUND";
      (error as ServiceError).status = 404;
      throw error;
    }

    const capabilities = mockCapabilities.get(targetId);
    if (!capabilities) {
      const error = new Error("Capabilities not discovered. Test connection first.");
      (error as ServiceError).code = "CAPABILITIES_NOT_DISCOVERED";
      throw error;
    }

    return capabilities;
  },

  /**
   * Refresh/discover target capabilities (tests connection).
   */
  async refreshCapabilities(targetId: string): Promise<TargetCapabilities> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS + 500));

    const target = mockTargets.get(targetId);
    if (!target) {
      const error = new Error(`Target not found: ${targetId}`);
      (error as ServiceError).code = "TARGET_NOT_FOUND";
      (error as ServiceError).status = 404;
      throw error;
    }

    // Simulate capability discovery based on adapter type
    const capabilities: TargetCapabilities = {
      target_id: targetId,
      capabilities: {
        protocol_version: "1.0",
        query: true,
        streaming: target.adapter === "http",
        conversation_history: true,
        retrieval: true,
        retrieval_stages: false,
        document_ingestion: target.adapter === "http",
        chunk_ingestion: false,
        context_injection: true,
        citations: true,
        confidence: false,
        target_trace: target.adapter === "http",
        effective_configuration: false,
        idempotency: true,
        request_recovery: false,
        usage: {
          tokens: true,
          cost: false,
          cpu: false,
          ram: false,
          gpu: false,
          vram: false,
        },
        retrieval_metadata: {
          rank: true,
          score: true,
          document_id: true,
          chunk_id: false,
          page: false,
          character_span: false,
        },
        limits: {
          max_query_length: 4096,
        },
        idempotency_retention_seconds: 3600,
      },
      discovered_at: new Date().toISOString(),
    };

    mockCapabilities.set(targetId, capabilities);
    return capabilities;
  },

  /**
   * Test target connection.
   */
  async testConnection(targetId: string): Promise<TargetConnectionTestResult> {
    initializeMockData();
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS + 300));

    const target = mockTargets.get(targetId);
    if (!target) {
      return {
        success: false,
        target_id: targetId,
        error: "Target not found",
        error_category: "NOT_FOUND",
        error_code: "TARGET_NOT_FOUND",
        tested_at: new Date().toISOString(),
      };
    }

    // Simulate connection test - always succeed for mock
    return {
      success: true,
      target_id: targetId,
      response_time_ms: Math.floor(Math.random() * 200) + 50, // 50-250ms
      tested_at: new Date().toISOString(),
    };
  },

  /**
   * Test connection for a draft target (before saving).
   */
  async testConnectionDraft(data: TargetCreate): Promise<TargetConnectionTestResult> {
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY_MS + 300));

    // Validate basic requirements
    if (data.adapter === "http" && !data.base_url) {
      return {
        success: false,
        target_id: "draft",
        error: "Base URL is required for HTTP adapter",
        error_category: "VALIDATION",
        error_code: "MISSING_BASE_URL",
        tested_at: new Date().toISOString(),
      };
    }

    if (data.adapter === "python" && !data.python_target) {
      return {
        success: false,
        target_id: "draft",
        error: "Python target is required for Python adapter",
        error_category: "VALIDATION",
        error_code: "MISSING_PYTHON_TARGET",
        tested_at: new Date().toISOString(),
      };
    }

    // Simulate successful connection for valid draft
    return {
      success: true,
      target_id: "draft",
      response_time_ms: Math.floor(Math.random() * 200) + 50,
      tested_at: new Date().toISOString(),
    };
  },
};
