/**
 * Centralized route definitions for RAG-Eval.
 *
 * This module defines all application routes in one place to avoid
 * scattered route strings throughout components.
 */

export const ROUTES = {
  // Top-level routes
  dashboard: "/",
  targets: "/targets",
  datasets: "/datasets",
  tests: "/tests",
  results: "/results",
  settings: "/settings",
  designSystem: "/design-system",

  // Detail routes
  targetDetail: (targetId: string) => `/targets/${targetId}`,
  datasetDetail: (datasetId: string) => `/datasets/${datasetId}`,
  testDetail: (testId: string) => `/tests/${testId}`,
  runDetail: (runId: string) => `/runs/${runId}`,
  runCaseDetail: (runId: string, caseId: string) => `/runs/${runId}/cases/${caseId}`,
} as const;

/**
 * Primary navigation configuration.
 * Used by Sidebar to render navigation items.
 */
export const PRIMARY_NAVIGATION = [
  { label: "Dashboard", path: ROUTES.dashboard, icon: "LayoutDashboard" as const },
  { label: "Targets", path: ROUTES.targets, icon: "Waypoints" as const },
  { label: "Datasets", path: ROUTES.datasets, icon: "Database" as const },
  { label: "Tests", path: ROUTES.tests, icon: "FlaskConical" as const },
  { label: "Results", path: ROUTES.results, icon: "BarChart" as const },
] as const;

/**
 * Secondary navigation configuration.
 * Rendered separately in sidebar (e.g., Settings).
 */
export const SECONDARY_NAVIGATION = [
  { label: "Settings", path: ROUTES.settings, icon: "Settings" as const },
] as const;
