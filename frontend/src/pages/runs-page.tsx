import { useParams } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { EmptyState } from "@/components/ui/empty-state";
import { ClipboardList } from "lucide-react";

/**
 * Run detail page - show evaluation run status and results.
 *
 * Placeholder for future run detail functionality.
 */
export function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();

  return (
    <Page>
      <Page.Header
        title={`Run: ${runId || ""}`}
        description="Evaluation run status and results."
        breadcrumbs={[{ label: "Runs", href: "/results" }]}
      />

      <Page.Content>
        <EmptyState
          icon={<ClipboardList className="h-8 w-8" />}
          title="Run not found"
          description="This evaluation run has not been recorded yet."
        />
      </Page.Content>
    </Page>
  );
}

/**
 * Case detail page - show individual case execution details.
 *
 * Placeholder for future case detail functionality.
 */
export function RunCaseDetailPage() {
  const { runId, caseId } = useParams<{ runId: string; caseId: string }>();

  return (
    <Page>
      <Page.Header
        title={`Case: ${caseId || ""}`}
        description={`Case execution details for run ${runId || ""}.`}
        breadcrumbs={[
          { label: "Runs", href: "/results" },
          { label: runId || "", href: `/runs/${runId || ""}` },
        ]}
      />

      <Page.Content>
        <EmptyState
          title="Case not found"
          description="This case execution has not been recorded yet."
        />
      </Page.Content>
    </Page>
  );
}
