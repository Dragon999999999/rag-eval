/**
 * Main RAG-Eval Dashboard page.
 *
 * Primary landing page showing:
 * - Active evaluations
 * - Latest results
 * - Recent runs
 * - Run comparisons
 * - Resource summaries
 * - Quick actions
 *
 * Handles multiple states:
 * - Loading
 * - First-use (no resources)
 * - Ready-to-evaluate (resources but no runs)
 * - Operational (full dashboard)
 * - Error
 */
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { useDashboardSummary } from "./use-dashboard";
import { DashboardSkeleton } from "./dashboard-skeleton";
import { DashboardError } from "./dashboard-error";
import { FirstUseState } from "./first-use-state";
import { ReadyToEvaluateState } from "./ready-state";
import { ResourceSummarySection } from "./resource-summary";
import { ActiveEvaluations } from "./active-evaluations";
import { LatestResults } from "./latest-results";
import { RecentRuns } from "./recent-runs";
import { RunComparison } from "./run-comparison";
import { QuickActions } from "./quick-actions";

export function DashboardPage() {
  const {
    data,
    isLoading,
    refetch,
    dashboardState,
  } = useDashboardSummary();

  // Loading state
  if (isLoading || dashboardState === "loading") {
    return (
      <Page>
        <Page.Header
          title="Evaluation Overview"
          description="Monitor evaluations and recent system performance."
          actions={
            <Button asChild>
              <Link to="/tests">New Evaluation</Link>
            </Button>
          }
        />
        <Page.Content>
          <DashboardSkeleton />
        </Page.Content>
      </Page>
    );
  }

  // Error state
  if (dashboardState === "error") {
    return (
      <Page>
        <Page.Header
          title="Evaluation Overview"
          description="Monitor evaluations and recent system performance."
        />
        <Page.Content>
          <DashboardError onRetry={() => void refetch()} />
        </Page.Content>
      </Page>
    );
  }

  // First-use state - no resources at all
  if (dashboardState === "first-use") {
    return (
      <Page>
        <Page.Header
          title="Evaluation Overview"
          description="Start evaluating your RAG system."
          actions={
            <Button asChild>
              <Link to="/tests">New Evaluation</Link>
            </Button>
          }
        />
        <Page.Content>
          <FirstUseState />
        </Page.Content>
      </Page>
    );
  }

  // Ready-to-evaluate state - resources exist but no runs
  if (dashboardState === "ready-to-evaluate") {
    return (
      <Page>
        <Page.Header
          title="Evaluation Overview"
          description="You have the prerequisites to run your first evaluation."
          actions={
            <Button asChild>
              <Link to="/tests">New Evaluation</Link>
            </Button>
          }
        />
        <Page.Content>
          <div className="space-y-6">
            {data && <ResourceSummarySection resources={data.resources} />}
            {data && <ReadyToEvaluateState resources={data.resources} />}
            <QuickActions />
          </div>
        </Page.Content>
      </Page>
    );
  }

  // Operational state - full dashboard
  return (
    <Page>
      <Page.Header
        title="Evaluation Overview"
        description="Monitor evaluation runs, regressions and system performance."
        actions={
          <Button asChild>
            <Link to="/tests">New Evaluation</Link>
          </Button>
        }
      />

      <Page.Content>
        <div className="space-y-8">
          {/* Resource Summary */}
          {data && <ResourceSummarySection resources={data.resources} />}

          {/* Active Evaluations */}
          {data && data.activeRuns.length > 0 && (
            <ActiveEvaluations activeRuns={data.activeRuns} />
          )}

          {/* Latest Results */}
          {data && data.latestCompletedRun && (
            <LatestResults latestRun={data.latestCompletedRun} />
          )}

          {/* Recent Runs */}
          {data && data.recentRuns.length > 0 && (
            <RecentRuns runs={data.recentRuns} />
          )}

          {/* Run Comparison */}
          {data && data.latestComparison && (
            <RunComparison comparison={data.latestComparison} />
          )}

          {/* Quick Actions */}
          <QuickActions />
        </div>
      </Page.Content>
    </Page>
  );
}
