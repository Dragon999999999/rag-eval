import { useParams } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { TestEditor } from "../components/test-editor";

/** Test view: editable configuration, readiness, current run, and history. */
export function TestDetailPage() {
  const { testId } = useParams<{ testId: string }>();
  return (
    <Page>
      <Page.Header
        title="Test"
        description="Configuration and execution state"
        breadcrumbs={[{ label: "Tests", href: "/tests" }]}
      />
      <Page.Content>{testId && <TestEditor testId={testId} />}</Page.Content>
    </Page>
  );
}
