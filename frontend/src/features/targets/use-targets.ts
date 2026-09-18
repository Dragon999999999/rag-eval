/**
 * TanStack Query hooks for target management.
 *
 * All server state is managed through TanStack Query.
 * Do not store fetched targets in Redux/global context.
 */
import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { TargetService } from "./target-service";
import type {
  Target,
  TargetCreate,
  TargetUpdate,
  TargetCapabilities,
} from "./target-types";

/**
 * Query key factory for targets.
 */
export const targetQueryKeys = {
  all: ["targets"] as const,
  lists: () => [...targetQueryKeys.all, "list"] as const,
  list: (filters: { status?: string; type?: string; search?: string }) =>
    [...targetQueryKeys.lists(), filters] as const,
  details: () => [...targetQueryKeys.all, "detail"] as const,
  detail: (targetId: string) => [...targetQueryKeys.details(), targetId] as const,
  capabilities: (targetId: string) =>
    [...targetQueryKeys.detail(targetId), "capabilities"] as const,
  connectionTest: (targetId: string) =>
    [...targetQueryKeys.detail(targetId), "connection"] as const,
};

/**
 * Hook to fetch list of targets.
 */
export function useTargetList(
  filters?: { status?: string; type?: string; search?: string },
  options?: Omit<UseQueryOptions<Target[]>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: targetQueryKeys.list(filters ?? {}),
    queryFn: () => TargetService.listTargets(),
    ...options,
  });
}

/**
 * Hook to fetch a single target by ID.
 */
export function useTarget(
  targetId: string,
  options?: Omit<UseQueryOptions<Target>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: targetQueryKeys.detail(targetId),
    queryFn: () => TargetService.getTarget(targetId),
    enabled: !!targetId,
    ...options,
  });
}

/**
 * Hook to create a new target.
 */
export function useCreateTarget(options?: {
  onSuccess?: (data: Target) => void;
  onError?: (error: Error) => void;
}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: TargetCreate) => TargetService.createTarget(data),
    onSuccess: (data) => {
      // Invalidate list and navigate to detail
      void queryClient.invalidateQueries({ queryKey: targetQueryKeys.lists() });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

/**
 * Hook to update a target.
 */
export function useUpdateTarget(
  targetId: string,
  options?: {
    onSuccess?: (data: Target) => void;
    onError?: (error: Error) => void;
  }
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: TargetUpdate) => TargetService.updateTarget(targetId, data),
    onSuccess: (data) => {
      // Invalidate detail and list
      void queryClient.invalidateQueries({ queryKey: targetQueryKeys.detail(targetId) });
      void queryClient.invalidateQueries({ queryKey: targetQueryKeys.lists() });
      options?.onSuccess?.(data);
    },
    onError: options?.onError,
  });
}

/**
 * Hook to delete a target.
 */
export function useDeleteTarget(options?: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (targetId: string) => {
      await TargetService.deleteTarget(targetId);
      return targetId;
    },
    onSuccess: (targetId) => {
      // Remove from cache and invalidate lists
      // eslint-disable-next-line @typescript-eslint/no-floating-promises
      queryClient.removeQueries({ queryKey: targetQueryKeys.detail(targetId) });
      // eslint-disable-next-line @typescript-eslint/no-floating-promises
      queryClient.invalidateQueries({ queryKey: targetQueryKeys.lists() });
      options?.onSuccess?.();
    },
    onError: options?.onError,
  });
}

/**
 * Hook to fetch target capabilities.
 */
export function useTargetCapabilities(
  targetId: string,
  options?: Omit<UseQueryOptions<TargetCapabilities>, "queryKey" | "queryFn">
) {
  return useQuery({
    queryKey: targetQueryKeys.capabilities(targetId),
    queryFn: () => TargetService.getCapabilities(targetId),
    enabled: !!targetId,
    ...options,
  });
}

/**
 * Hook to refresh/test target capabilities (tests connection).
 */
export function useRefreshCapabilities(options?: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (targetId: string) => {
      const capabilities = await TargetService.refreshCapabilities(targetId);
      // Update capabilities cache
      queryClient.setQueryData(targetQueryKeys.capabilities(targetId), capabilities);
      return capabilities;
    },
    onSuccess: () => {
      options?.onSuccess?.();
    },
    onError: options?.onError,
  });
}

/**
 * Hook to test target connection.
 */
export function useTestConnection(options?: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}) {
  return useMutation({
    mutationFn: async (targetId: string) => {
      return await TargetService.testConnection(targetId);
    },
    onSuccess: () => {
      options?.onSuccess?.();
    },
    onError: options?.onError,
  });
}

/**
 * Hook to test connection for a draft target.
 */
export function useTestConnectionDraft(options?: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}) {
  return useMutation({
    mutationFn: async (data: TargetCreate) => {
      return await TargetService.testConnectionDraft(data);
    },
    onSuccess: () => {
      options?.onSuccess?.();
    },
    onError: options?.onError,
  });
}
