/**
 * Datasets list page - /datasets
 */
import { Link } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Badge } from "@/components/ui/badge";
import { useDatasetList } from "../use-datasets";
import { formatCaseCount, formatRelativeTime } from "../dataset-formatters";
import type { DatasetInfo } from "../dataset-types";

export function DatasetsPage() {
  const { data: datasets, isLoading, error, refetch } = useDatasetList();

  if (isLoading) {
    return (
      <Page>
        <Page.Header
          title="Datasets"
          description="Manage benchmark datasets and evaluation cases."
          actions={
            <Button asChild>
              <Link to="/datasets/new">New Dataset</Link>
            </Button>
          }
        />
        <Page.Content>
          <DatasetListSkeleton />
        </Page.Content>
      </Page>
    );
  }

  if (error) {
    return (
      <Page>
        <Page.Header
          title="Datasets"
          description="Manage benchmark datasets and evaluation cases."
          actions={
            <Button asChild>
              <Link to="/datasets/new">New Dataset</Link>
            </Button>
          }
        />
        <Page.Content>
          <EmptyState
            title="Unable to load datasets"
            description="An error occurred while fetching datasets."
            action={
              <Button variant="secondary" onClick={() => refetch()}>
                Retry
              </Button>
            }
          />
        </Page.Content>
      </Page>
    );
  }

  if (!datasets || datasets.length === 0) {
    return (
      <Page>
        <Page.Header
          title="Datasets"
          description="Create and manage reusable evaluation benchmark sets."
          actions={
            <Button asChild>
              <Link to="/datasets/new">New Dataset</Link>
            </Button>
          }
        />
        <Page.Content>
          <EmptyState
            title="Create your first evaluation dataset"
            description="Datasets contain benchmark queries, reference answers, gold evidence and metadata used to evaluate targets."
            action={
              <Button asChild>
                <Link to="/datasets/new">Create Dataset</Link>
              </Button>
            }
          />
        </Page.Content>
      </Page>
    );
  }

  return (
    <Page>
      <Page.Header
        title="Datasets"
        description="Create and manage reusable evaluation benchmark sets."
        actions={
          <Button asChild>
            <Link to="/datasets/new">New Dataset</Link>
          </Button>
        }
      />

      <Page.Content>
        <Surface>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Version</TableHead>
                <TableHead>Cases</TableHead>
                <TableHead>Tags</TableHead>
                <TableHead>Updated</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {datasets.map((dataset) => (
                <DatasetRow key={dataset.dataset_id} dataset={dataset} />
              ))}
            </TableBody>
          </Table>
        </Surface>
      </Page.Content>
    </Page>
  );
}

interface DatasetRowProps {
  dataset: DatasetInfo;
}

function DatasetRow({ dataset }: DatasetRowProps) {
  return (
    <TableRow>
      <TableCell>
        <div>
          <div className="font-medium text-text-primary">{dataset.name}</div>
          {dataset.source && (
            <div className="text-xs text-text-tertiary">{dataset.source}</div>
          )}
        </div>
      </TableCell>
      <TableCell>
        <span className="text-sm text-text-secondary">{dataset.version}</span>
      </TableCell>
      <TableCell>
        <span className="text-sm text-text-primary">
          {formatCaseCount(dataset.case_count)}
        </span>
      </TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-1">
          {dataset.tags.slice(0, 3).map((tag) => (
            <Badge key={tag} variant="default">
              {tag}
            </Badge>
          ))}
          {dataset.tags.length > 3 && (
            <span className="text-xs text-text-tertiary">
              +{dataset.tags.length - 3}
            </span>
          )}
        </div>
      </TableCell>
      <TableCell>
        <span className="text-sm text-text-tertiary">
          {formatRelativeTime(dataset.updated_at)}
        </span>
      </TableCell>
      <TableCell className="text-right">
        <Button variant="ghost" size="sm" asChild>
          <Link to={`/datasets/${dataset.dataset_id}`}>Open</Link>
        </Button>
      </TableCell>
    </TableRow>
  );
}

function DatasetListSkeleton() {
  return (
    <Surface>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Version</TableHead>
            <TableHead>Cases</TableHead>
            <TableHead>Tags</TableHead>
            <TableHead>Updated</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {[...Array(5)].map((_, i) => (
            <TableRow key={i}>
              <TableCell>
                <Skeleton className="h-4 w-32" />
              </TableCell>
              <TableCell>
                <Skeleton className="h-4 w-12" />
              </TableCell>
              <TableCell>
                <Skeleton className="h-4 w-20" />
              </TableCell>
              <TableCell>
                <div className="flex gap-1">
                  <Skeleton className="h-4 w-12" />
                  <Skeleton className="h-4 w-12" />
                </div>
              </TableCell>
              <TableCell>
                <Skeleton className="h-4 w-16" />
              </TableCell>
              <TableCell>
                <Skeleton className="ml-auto h-7 w-14" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Surface>
  );
}
