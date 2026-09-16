/**
 * Targets list page - /targets
 *
 * Main page for managing RAG/LLM evaluation targets.
 */
import { Link } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { TargetList } from "../components/target-list";

export function TargetsPage() {
  return (
    <Page>
      <Page.Header
        title="Targets"
        description="Connect RAG systems and LLM endpoints that can be evaluated."
        actions={
          <Button asChild>
            <Link to="/targets/new">Add Target</Link>
          </Button>
        }
      />

      <Page.Content>
        <TargetList />
      </Page.Content>
    </Page>
  );
}
