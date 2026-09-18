import { createBrowserRouter, type RouteObject } from "react-router-dom";
import { AppShell } from "@/components/layout/app-shell";
import { DesignSystemShowcase } from "@/app/design-system/showcase";
import { DashboardPage } from "@/pages/dashboard-page";
import { TargetsPage, TargetDetailPage } from "@/pages/targets-page";
import { TargetCreatePage } from "@/features/targets/pages/target-create-page";
import { TargetEditPage } from "@/features/targets/pages/target-edit-page";
import { DatasetsPage, DatasetDetailPage } from "@/pages/datasets-page";
import { DatasetCreatePage } from "@/features/datasets/pages/dataset-create-page";
import { TestsPage, TestDetailPage, TestCreatePage, TestEditPage } from "@/pages/tests-page";
import { ResultsPage } from "@/pages/results-page";
import { RunDetailPage, RunCaseDetailPage } from "@/pages/runs-page";
import { RunComparePage } from "@/pages/runs-page";
import { SettingsPage } from "@/pages/settings-page";
import { NotFoundPage, ErrorBoundaryPage } from "@/pages/error-page";

/**
 * Application route configuration.
 *
 * All routes are defined centrally here. The AppShell wraps all product routes,
 * while /design-system remains outside the main application shell.
 */
const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    errorElement: <ErrorBoundaryPage />,
    children: [
      // Top-level routes
      { index: true, element: <DashboardPage /> },
      { path: "design-system", element: <DesignSystemShowcase /> },

      // Targets
      { path: "targets", element: <TargetsPage /> },
      { path: "targets/new", element: <TargetCreatePage /> },
      { path: "targets/:targetId", element: <TargetDetailPage /> },
      { path: "targets/:targetId/edit", element: <TargetEditPage /> },

      // Datasets
      { path: "datasets", element: <DatasetsPage /> },
      { path: "datasets/new", element: <DatasetCreatePage /> },
      { path: "datasets/:datasetId", element: <DatasetDetailPage /> },

      // Tests
      { path: "tests", element: <TestsPage /> },
      { path: "tests/new", element: <TestCreatePage /> },
      { path: "tests/:testId", element: <TestDetailPage /> },
      { path: "tests/:testId/edit", element: <TestEditPage /> },

      // Results / Runs
      { path: "results", element: <ResultsPage /> },
      { path: "runs/:runId", element: <RunDetailPage /> },
      {
        path: "runs/:runId/cases/:caseId",
        element: <RunCaseDetailPage />,
      },
      {
        path: "runs/:runId/compare/:otherRunId",
        element: <RunComparePage />,
      },

      // Settings
      { path: "settings", element: <SettingsPage /> },

      // 404 - catch-all for unknown routes
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export function createRouter() {
  return createBrowserRouter(routes, {
    basename: "/",
  });
}
