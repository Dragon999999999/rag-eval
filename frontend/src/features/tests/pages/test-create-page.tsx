/**
 * Test creation page - wraps the TestBuilder wizard.
 */
import { Page } from "@/components/layout/page-layout";
import { TestBuilder } from "../builder/test-builder";

export function TestCreatePage() {
  return (
    <Page>
      <Page.Header
        title="Create New Test"
        description="Define a new evaluation test by selecting a target, dataset, and metrics."
        breadcrumbs={[{ label: "Tests", href: "/tests" }]}
      />

      <Page.Content>
        <TestBuilder />
      </Page.Content>
    </Page>
  );
}
