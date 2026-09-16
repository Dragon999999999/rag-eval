import { useParams } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Waypoints } from "lucide-react";

/**
 * Targets page - manage RAG/LLM systems to evaluate.
 *
 * Placeholder for future target management functionality.
 */
export function TargetsPage() {
  return (
    <Page>
      <Page.Header
        title="Targets"
        description="Connect RAG or LLM systems that you want to evaluate."
        actions={
          <Button>
            <span className="mr-2">+</span>
            Add Target
          </Button>
        }
      />

      <Page.Content>
        <EmptyState
          icon={<Waypoints className="h-8 w-8" />}
          title="No targets configured"
          description="Add a target to begin evaluating a RAG or LLM system."
          action={
            <Button variant="secondary">Add Target</Button>
          }
        />
      </Page.Content>
    </Page>
  );
}

/**
 * Target detail page placeholder.
 */
export function TargetDetailPage() {
  const { targetId } = useParams<{ targetId: string }>();

  return (
    <Page>
      <Page.Header
        title={`Target: ${targetId || ""}`}
        description="Target configuration and evaluation history."
        breadcrumbs={[{ label: "Targets", href: "/targets" }]}
      />

      <Page.Content>
        <EmptyState
          title="Target not found"
          description="This target has not been configured yet."
        />
      </Page.Content>
    </Page>
  );
}
