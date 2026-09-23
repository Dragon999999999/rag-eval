import { useParams } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { TestEditor } from "../components/test-editor";

/** Editable persisted test configuration. */
export function TestEditPage() {
  const { testId } = useParams<{ testId: string }>();
  return (
    <Page>
      <Page.Header
        title="Configure test"
        description="Configure the saved test, validate readiness, and monitor its latest run."
        breadcrumbs={[{ label: "Tests", href: "/tests" }, { label: testId ?? "" }]}
      />
      <Page.Content>{testId && <TestEditor testId={testId} />}</Page.Content>
    </Page>
  );
}
