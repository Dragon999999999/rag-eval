import { useParams } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Database } from "lucide-react";

/**
 * Datasets page - manage benchmark datasets.
 *
 * Placeholder for future dataset management functionality.
 */
export function DatasetsPage() {
  return (
    <Page>
      <Page.Header
        title="Datasets"
        description="Manage benchmark datasets and evaluation cases."
        actions={
          <Button>
            <span className="mr-2">+</span>
            Add Dataset
          </Button>
        }
      />

      <Page.Content>
        <EmptyState
          icon={<Database className="h-8 w-8" />}
          title="No datasets available"
          description="Upload or import a dataset to begin creating evaluations."
          action={
            <Button variant="secondary">Add Dataset</Button>
          }
        />
      </Page.Content>
    </Page>
  );
}

/**
 * Dataset detail page placeholder.
 */
export function DatasetDetailPage() {
  const { datasetId } = useParams<{ datasetId: string }>();

  return (
    <Page>
      <Page.Header
        title={`Dataset: ${datasetId || ""}`}
        description="Dataset configuration and case management."
        breadcrumbs={[{ label: "Datasets", href: "/datasets" }]}
      />

      <Page.Content>
        <EmptyState
          title="Dataset not found"
          description="This dataset has not been configured yet."
        />
      </Page.Content>
    </Page>
  );
}
