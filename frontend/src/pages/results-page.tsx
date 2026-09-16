import { Page } from "@/components/layout/page-layout";
import { EmptyState } from "@/components/ui/empty-state";
import { BarChart } from "lucide-react";

/**
 * Results page - review completed evaluations.
 *
 * Placeholder for future results analysis and comparison functionality.
 */
export function ResultsPage() {
  return (
    <Page>
      <Page.Header
        title="Results"
        description="Review completed evaluations and compare system performance."
      />

      <Page.Content>
        <EmptyState
          icon={<BarChart className="h-8 w-8" />}
          title="No evaluation results yet"
          description="Run evaluations to see results and analysis here."
        />
      </Page.Content>
    </Page>
  );
}
