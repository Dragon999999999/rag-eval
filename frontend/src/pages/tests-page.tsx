import { useParams } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { FlaskConical } from "lucide-react";

/**
 * Tests page - define evaluations by combining target, dataset, and metrics.
 *
 * Placeholder for future TestDefinition management functionality.
 */
export function TestsPage() {
  return (
    <Page>
      <Page.Header
        title="Tests"
        description="Define evaluations by combining a target, dataset, and metric configuration."
        actions={
          <Button>
            <span className="mr-2">+</span>
            New Test
          </Button>
        }
      />

      <Page.Content>
        <EmptyState
          icon={<FlaskConical className="h-8 w-8" />}
          title="No tests configured"
          description="Create a test to define an evaluation configuration."
          action={
            <Button variant="secondary">New Test</Button>
          }
        />
      </Page.Content>
    </Page>
  );
}

/**
 * Test detail page placeholder.
 */
export function TestDetailPage() {
  const { testId } = useParams<{ testId: string }>();

  return (
    <Page>
      <Page.Header
        title={`Test: ${testId || ""}`}
        description="Test configuration and execution history."
        breadcrumbs={[{ label: "Tests", href: "/tests" }]}
      />

      <Page.Content>
        <EmptyState
          title="Test not found"
          description="This test has not been configured yet."
        />
      </Page.Content>
    </Page>
  );
}
