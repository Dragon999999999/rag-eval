/** TanStack Query hooks for the target-management API. */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { TargetService } from "./target-service";
import type {
  Target,
  TargetAdapterInfo,
  TargetAdapterSourceInfo,
  TargetCapabilitiesInfo,
  TargetConfigVersionInfo,
  TargetConfigurationResponse,
  TargetConnectionInfo,
  TargetCreate,
  TargetSummary,
  TargetUpdate,
} from "./target-types";

export const targetQueryKeys = {
  all: ["targets"] as const,
  list: () => [...targetQueryKeys.all, "list"] as const,
  detail: (id: string) => [...targetQueryKeys.all, "detail", id] as const,
  adapters: () => [...targetQueryKeys.all, "adapters"] as const,
  configuration: (id: string) =>
    [...targetQueryKeys.detail(id), "configuration"] as const,
  versions: (id: string) => [...targetQueryKeys.detail(id), "versions"] as const,
  version: (id: string, version: number) =>
    [...targetQueryKeys.versions(id), version] as const,
  source: (id: string) => [...targetQueryKeys.detail(id), "source"] as const,
  connection: (id: string) => [...targetQueryKeys.detail(id), "connection"] as const,
  capabilities: (id: string) =>
    [...targetQueryKeys.detail(id), "capabilities"] as const,
};

export function useTargetList(
  options?: Omit<UseQueryOptions<TargetSummary[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: targetQueryKeys.list(),
    queryFn: () => TargetService.listTargets(),
    ...options,
  });
}

export function useTarget(
  targetId: string,
  options?: Omit<UseQueryOptions<Target>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: targetQueryKeys.detail(targetId),
    queryFn: () => TargetService.getTarget(targetId),
    enabled: Boolean(targetId),
    ...options,
  });
}

export function useTargetAdapters(
  options?: Omit<UseQueryOptions<TargetAdapterInfo[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: targetQueryKeys.adapters(),
    queryFn: () => TargetService.listAdapters(),
    staleTime: 300_000,
    ...options,
  });
}

export function useTargetConfiguration(
  targetId: string,
  options?: Omit<UseQueryOptions<TargetConfigurationResponse>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: targetQueryKeys.configuration(targetId),
    queryFn: () => TargetService.getConfiguration(targetId),
    enabled: Boolean(targetId),
    ...options,
  });
}

export function useTargetConfigurationVersions(
  targetId: string,
  options?: Omit<UseQueryOptions<TargetConfigVersionInfo[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: targetQueryKeys.versions(targetId),
    queryFn: () => TargetService.listConfigurationVersions(targetId),
    enabled: Boolean(targetId),
    ...options,
  });
}

export function useTargetAdapterSource(
  targetId: string,
  options?: Omit<UseQueryOptions<TargetAdapterSourceInfo>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: targetQueryKeys.source(targetId),
    queryFn: () => TargetService.getPythonAdapterSource(targetId),
    enabled: Boolean(targetId),
    ...options,
  });
}

export function useTargetConnection(
  targetId: string,
  options?: Omit<UseQueryOptions<TargetConnectionInfo>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: targetQueryKeys.connection(targetId),
    queryFn: () => TargetService.getConnection(targetId),
    enabled: Boolean(targetId),
    ...options,
  });
}

export function useTargetCapabilities(
  targetId: string,
  options?: Omit<UseQueryOptions<TargetCapabilitiesInfo>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: targetQueryKeys.capabilities(targetId),
    queryFn: () => TargetService.getCapabilities(targetId),
    enabled: Boolean(targetId),
    ...options,
  });
}

function invalidateTarget(client: ReturnType<typeof useQueryClient>, id?: string) {
  void client.invalidateQueries({ queryKey: targetQueryKeys.list() });
  if (id) void client.invalidateQueries({ queryKey: targetQueryKeys.detail(id) });
}

export function useCreateTarget(options?: {
  onSuccess?: (data: Target) => void;
  onError?: (error: Error) => void;
}) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: TargetCreate) => TargetService.createTarget(data),
    onSuccess: (data) => {
      invalidateTarget(client);
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

export function useUpdateTarget(
  targetId: string,
  options?: { onSuccess?: (data: Target) => void; onError?: (error: Error) => void }
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: TargetUpdate) => TargetService.updateTarget(targetId, data),
    onSuccess: (data) => {
      invalidateTarget(client, targetId);
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

export function useDeleteTarget(options?: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await TargetService.deleteTarget(id);
      return id;
    },
    onSuccess: (id) => {
      client.removeQueries({ queryKey: targetQueryKeys.detail(id) });
      invalidateTarget(client);
      options?.onSuccess?.();
    },
    onError: options?.onError,
  });
}

export function useSaveTargetConfiguration(
  targetId: string,
  options?: { onSuccess?: () => void; onError?: (error: Error) => void }
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (yaml: string) => TargetService.saveConfiguration(targetId, yaml),
    onSuccess: () => {
      invalidateTarget(client, targetId);
      void client.invalidateQueries({
        queryKey: targetQueryKeys.configuration(targetId),
      });
      void client.invalidateQueries({ queryKey: targetQueryKeys.versions(targetId) });
      void client.invalidateQueries({ queryKey: targetQueryKeys.connection(targetId) });
      options?.onSuccess?.();
    },
    onError: (error) => {
      // The backend records INVALID for a first failed configuration, so
      // refresh the summary even when the mutation itself returns 422.
      invalidateTarget(client, targetId);
      options?.onError?.(error);
    },
  });
}

export function useUploadPythonAdapter(
  targetId: string,
  options?: {
    onSuccess?: (data: TargetAdapterSourceInfo) => void;
    onError?: (error: Error) => void;
  }
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => TargetService.uploadPythonAdapter(targetId, file),
    onSuccess: (data) => {
      invalidateTarget(client, targetId);
      void client.invalidateQueries({ queryKey: targetQueryKeys.source(targetId) });
      void client.invalidateQueries({ queryKey: targetQueryKeys.versions(targetId) });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

export function useTestConnection(options?: {
  onSuccess?: (data: TargetConnectionInfo) => void;
  onError?: (error: Error) => void;
}) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => TargetService.testConnection(id),
    onSuccess: (data) => {
      void client.invalidateQueries({ queryKey: targetQueryKeys.all });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

export function useDiscoverCapabilities(options?: {
  onSuccess?: (data: TargetCapabilitiesInfo) => void;
  onError?: (error: Error) => void;
}) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => TargetService.discoverCapabilities(id),
    onSuccess: (data) => {
      invalidateTarget(client, data.target_id);
      void client.invalidateQueries({
        queryKey: targetQueryKeys.capabilities(data.target_id),
      });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}
