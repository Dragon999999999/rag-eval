/**
 * Test edit page - wraps the TestBuilder wizard with existing test data.
 */
import { useParams } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { TestBuilder } from "../builder/test-builder";

export function TestEditPage() {
  const { testId } = useParams<{ testId: string }>();

  return (
    <Page>
      <Page.Header
        title="Edit Test"
        description="Modify the test configuration."
        breadcrumbs={[
          { label: "Tests", href: "/tests" },
          { label: testId || "", href: `/tests/${testId}` },
        ]}
      />

      <Page.Content>
        <TestBuilder testDefinitionId={testId || ""} />
      </Page.Content>
    </Page>
  );
}
