/**
 * Dashboard service boundary.
 *
 * Provides a clean API for fetching dashboard data.
 * Currently uses mock implementation - can be replaced with
 * real HTTP implementation without changing dashboard components.
 */
import type { DashboardSummary } from "./dashboard-types";
import {
  getMockDashboardSummary,
  getMockEmptyDashboard,
  getMockReadyDashboard,
} from "./mocks";

/**
 * Fetch dashboard summary data.
 *
 * In production, this would call:
 * GET /api/v1/dashboard
 */
export async function getDashboardSummary(): Promise<DashboardSummary> {
  // Simulate network delay for realistic loading states
  await new Promise((resolve) => setTimeout(resolve, 500));

  // Return mock data - replace with real API call when backend exists
  return getMockDashboardSummary();
}

/**
 * Fetch empty dashboard state for testing.
 */
export async function getEmptyDashboard(): Promise<DashboardSummary> {
  await new Promise((resolve) => setTimeout(resolve, 300));
  return getMockEmptyDashboard();
}

/**
 * Fetch ready-to-evaluate state for testing.
 */
export async function getReadyDashboard(): Promise<DashboardSummary> {
  await new Promise((resolve) => setTimeout(resolve, 300));
  return getMockReadyDashboard();
}
