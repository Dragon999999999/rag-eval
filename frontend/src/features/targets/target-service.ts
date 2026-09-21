/** HTTP client for the evaluator-managed target API. */
import { apiRequest } from "@/lib/api/client";
import type {
  Target,
  TargetAdapterInfo,
  TargetAdapterSourceInfo,
  TargetCapabilitiesInfo,
  TargetConfigVersionDetail,
  TargetConfigVersionInfo,
  TargetConfigurationResponse,
  TargetConnectionInfo,
  TargetCreate,
  TargetSummary,
  TargetUpdate,
} from "./target-types";

function fileForm(file: File): FormData {
  const form = new FormData();
  form.append("file", file, file.name);
  return form;
}

export const TargetService = {
  async listTargets(): Promise<TargetSummary[]> {
    return apiRequest<TargetSummary[]>("/api/v1/targets");
  },
  async getTarget(targetId: string): Promise<Target> {
    return apiRequest<Target>(`/api/v1/targets/${encodeURIComponent(targetId)}`);
  },
  async createTarget(data: TargetCreate): Promise<Target> {
    return apiRequest<Target>("/api/v1/targets", { method: "POST", body: data });
  },
  async updateTarget(targetId: string, data: TargetUpdate): Promise<Target> {
    return apiRequest<Target>(`/api/v1/targets/${encodeURIComponent(targetId)}`, {
      method: "PATCH",
      body: data,
    });
  },
  async deleteTarget(targetId: string): Promise<undefined> {
    await apiRequest<undefined>(`/api/v1/targets/${encodeURIComponent(targetId)}`, {
      method: "DELETE",
    });
  },
  async listAdapters(): Promise<TargetAdapterInfo[]> {
    return apiRequest<TargetAdapterInfo[]>("/api/v1/targets/adapters");
  },
  async getConfiguration(targetId: string): Promise<TargetConfigurationResponse> {
    return apiRequest<TargetConfigurationResponse>(
      `/api/v1/targets/${encodeURIComponent(targetId)}/configuration`
    );
  },
  async saveConfiguration(
    targetId: string,
    yaml: string
  ): Promise<TargetConfigVersionInfo> {
    return apiRequest<TargetConfigVersionInfo>(
      `/api/v1/targets/${encodeURIComponent(targetId)}/configuration`,
      { method: "PUT", body: yaml, headers: { "Content-Type": "application/yaml" } }
    );
  },
  async listConfigurationVersions(
    targetId: string
  ): Promise<TargetConfigVersionInfo[]> {
    return apiRequest<TargetConfigVersionInfo[]>(
      `/api/v1/targets/${encodeURIComponent(targetId)}/configuration/versions`
    );
  },
  async getConfigurationVersion(
    targetId: string,
    version: number
  ): Promise<TargetConfigVersionDetail> {
    return apiRequest<TargetConfigVersionDetail>(
      `/api/v1/targets/${encodeURIComponent(targetId)}/configuration/versions/${String(version)}`
    );
  },
  async restoreConfigurationVersion(
    targetId: string,
    version: number
  ): Promise<TargetConfigVersionInfo> {
    return apiRequest<TargetConfigVersionInfo>(
      `/api/v1/targets/${encodeURIComponent(targetId)}/configuration/versions/${String(version)}/restore`,
      { method: "POST" }
    );
  },
  async uploadPythonAdapter(
    targetId: string,
    file: File
  ): Promise<TargetAdapterSourceInfo> {
    return apiRequest<TargetAdapterSourceInfo>(
      `/api/v1/targets/${encodeURIComponent(targetId)}/adapter-source`,
      { method: "POST", body: fileForm(file) }
    );
  },
  async getPythonAdapterSource(targetId: string): Promise<TargetAdapterSourceInfo> {
    return apiRequest<TargetAdapterSourceInfo>(
      `/api/v1/targets/${encodeURIComponent(targetId)}/adapter-source`
    );
  },
  async testConnection(targetId: string): Promise<TargetConnectionInfo> {
    return apiRequest<TargetConnectionInfo>(
      `/api/v1/targets/${encodeURIComponent(targetId)}/connection-test`,
      { method: "POST" }
    );
  },
  async getConnection(targetId: string): Promise<TargetConnectionInfo> {
    return apiRequest<TargetConnectionInfo>(
      `/api/v1/targets/${encodeURIComponent(targetId)}/connection`
    );
  },
  async discoverCapabilities(targetId: string): Promise<TargetCapabilitiesInfo> {
    return apiRequest<TargetCapabilitiesInfo>(
      `/api/v1/targets/${encodeURIComponent(targetId)}/capabilities/discover`,
      { method: "POST" }
    );
  },
  async getCapabilities(targetId: string): Promise<TargetCapabilitiesInfo> {
    return apiRequest<TargetCapabilitiesInfo>(
      `/api/v1/targets/${encodeURIComponent(targetId)}/capabilities`
    );
  },
};
