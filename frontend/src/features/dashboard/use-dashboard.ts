/**
 * TanStack Query hook for dashboard data.
 *
 * Centralized data fetching with loading, error, and polling logic.
 */
import { useQuery } from "@tanstack/react-query";
import { getDashboardSummary } from "./dashboard-service";
import type { DashboardState } from "./dashboard-types";

/**
 * Query key for dashboard summary.
 */
export const dashboardQueryKeys = {
  all: ["dashboard"] as const,
  summary: () => [...dashboardQueryKeys.all, "summary"] as const,
};

/**
 * Hook to fetch dashboard summary data.
 *
 * Features:
 * - Automatic loading/error states
 * - Polling when active runs exist
 * - Stale time for performance
 */
export function useDashboardSummary() {
  const { data, isLoading, error, refetch, isRefetching } = useQuery({
    queryKey: dashboardQueryKeys.summary(),
    queryFn: getDashboardSummary,
    staleTime: 1000 * 30, // 30 seconds
    refetchInterval: (query) => {
      const state = query.state.data;
      // Poll every 5 seconds if active runs exist
      if (state && state.activeRuns.length > 0) {
        return 5000;
      }
      // No polling when no active runs
      return false;
    },
  });

  // Determine dashboard state
  let dashboardState: DashboardState = "loading";

  if (isLoading || isRefetching) {
    dashboardState = "loading";
  } else if (error) {
    dashboardState = "error";
  } else if (data) {
    const { resources, recentRuns, latestCompletedRun } = data;

    // First-use: no resources at all
    if (
      resources.targets.total === 0 &&
      resources.datasets.total === 0 &&
      resources.tests.total === 0
    ) {
      dashboardState = "first-use";
    }
    // Ready-to-evaluate: resources exist but no runs
    else if (!latestCompletedRun && recentRuns.length === 0) {
      dashboardState = "ready-to-evaluate";
    }
    // Operational: has run data
    else {
      dashboardState = "operational";
    }
  }

  return {
    data,
    isLoading,
    error,
    refetch,
    isRefetching,
    dashboardState,
  };
}
