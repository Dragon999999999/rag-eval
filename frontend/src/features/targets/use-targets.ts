/** TanStack Query hooks for the target-management API. */
import { useEffect, useRef } from "react";
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

/**
 * How often, while a target-health view is mounted, to re-run live connection
 * checks. The persisted connection state can go stale (e.g. after a target's
 * endpoint changes or goes down weeks after the last manual test), so the
 * health lights are refreshed periodically without hammering endpoints.
 */
const DEFAULT_HEALTH_REFRESH_MS = 60 * 60 * 1000; // 1 hour

interface UseTargetListOptions
  extends Omit<UseQueryOptions<TargetSummary[]>, "queryKey" | "queryFn"> {
  /**
   * Re-run live connection health checks when targets first load and then on
   * `healthRefreshMs` while the view stays mounted. Defaults to true.
   */
  autoHealthCheck?: boolean;
  /** Interval between automatic connection checks while mounted. */
  healthRefreshMs?: number;
}

/**
 * Whether a target can meaningfully be health-checked: it must be enabled and
 * have a saved configuration version to build an adapter from.
 */
function healthCheckable(target: TargetSummary): boolean {
  return target.enabled && target.current_config_version != null;
}

export function useTargetList(options?: UseTargetListOptions) {
  const client = useQueryClient();
  const query = useQuery<TargetSummary[]>({
    queryKey: targetQueryKeys.list(),
    queryFn: () => TargetService.listTargets(),
    ...(options as UseQueryOptions<TargetSummary[]>),
  });

  const autoHealthCheck = options?.autoHealthCheck ?? true;
  const healthRefreshMs = options?.healthRefreshMs ?? DEFAULT_HEALTH_REFRESH_MS;

  // Keep the latest list reachable from the refresh effect without re-running
  // it on every refetch, which would otherwise trigger a check loop.
  const targetsRef = useRef<TargetSummary[] | undefined>(undefined);
  targetsRef.current = query.data;

  // Guards the on-mount check so it fires once even if the effect re-runs when
  // the refetched list arrives (React StrictMode re-invokes effects in dev).
  const mountChecked = useRef(false);

  useEffect(() => {
    if (!autoHealthCheck) return;

    const recheck = () => {
      const checkable = (targetsRef.current ?? []).filter(healthCheckable);
      if (!checkable.length) return;

      void Promise.all(
        checkable.map((target) =>
          TargetService.testConnection(target.target_id).catch(() => undefined)
        )
      ).then(() => {
        // Persisted states were refreshed server-side; refetch so the status
        // lights reflect the new results.
        void client.invalidateQueries({ queryKey: targetQueryKeys.list() });
      });
    };

    // Fresh check on page load: once targets are available, replace the stale
    // persisted light with current connectivity before the interval fires.
    if (
      !mountChecked.current &&
      (targetsRef.current ?? []).some(healthCheckable)
    ) {
      mountChecked.current = true;
      recheck();
    }

    const handle = window.setInterval(recheck, healthRefreshMs);
    return () => window.clearInterval(handle);
  }, [autoHealthCheck, healthRefreshMs, client, query.data]);

  return query;
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
