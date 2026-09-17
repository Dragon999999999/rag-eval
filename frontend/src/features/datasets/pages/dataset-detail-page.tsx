/**
 * Dataset detail page - /datasets/:datasetId
 */
import { useState } from "react";
import { useParams, Link, useSearchParams } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import { EmptyState } from "@/components/ui/empty-state";
import { Spinner } from "@/components/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SearchInput } from "@/components/ui/search-input";
import { StatusBadge } from "@/components/ui/status-badge";
import { Badge } from "@/components/ui/badge";
import { useDataset, useCaseList, useDeleteDataset, useValidateDataset } from "../use-datasets";
import {
  formatCaseCount,
  formatRelativeTime,
  truncateQuery,
  formatAnswerability,
  getAnswerabilityVariant,
} from "../dataset-formatters";
import { toast } from "@/lib/toast";
import { Database, Trash2 } from "lucide-react";
import { Dialog, DialogTrigger, DialogPortal, DialogOverlay, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";

export function DatasetDetailPage() {
  const { datasetId } = useParams<{ datasetId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  
  const search = searchParams.get("search") ?? "";
  const page = parseInt(searchParams.get("page") ?? "1", 10) || 1;
  const limit = 20;

  const {
    data: dataset,
    isLoading: isLoadingDataset,
    error: datasetError,
  } = useDataset(datasetId ?? "");

  const {
    data: caseData,
    isLoading: isLoadingCases,
  } = useCaseList(datasetId ?? "", {
    limit,
    offset: (page - 1) * limit,
    search: search || undefined,
  });

  const deleteDataset = useDeleteDataset({
    onSuccess: () => {
      toast.success("Dataset deleted");
      window.location.href = "/datasets";
    },
    onError: (error) => {
      toast.error(`Failed to delete dataset: ${error.message}`);
    },
  });

  const validateDataset = useValidateDataset({
    onSuccess: (result) => {
      toast.success(`Validation complete: ${result.valid_cases}/${result.total_cases} cases valid`);
    },
  });

  const handleDelete = () => {
    if (datasetId) {
      deleteDataset.mutate(datasetId);
      setShowDeleteDialog(false);
    }
  };

  const handleSearch = (value: string) => {
    const newParams = new URLSearchParams(searchParams);
    if (value) {
      newParams.set("search", value);
    } else {
      newParams.delete("search");
    }
    newParams.set("page", "1");
    setSearchParams(newParams);
  };

  if (isLoadingDataset) {
    return (
      <Page>
        <Page.Header title="Loading..." description="Loading dataset..." />
        <Page.Content>
          <Spinner />
        </Page.Content>
      </Page>
    );
  }

  if (datasetError || !dataset) {
    return (
      <Page>
        <Page.Header
          title="Dataset not found"
          description="The requested dataset does not exist."
          actions={
            <Button variant="secondary" asChild>
              <Link to="/datasets">Back to Datasets</Link>
            </Button>
          }
        />
        <Page.Content>
          <EmptyState
            icon={<Database className="h-8 w-8" />}
            title="Dataset not found"
            description="This dataset may have been deleted."
            action={
              <Button asChild>
                <Link to="/datasets">Browse Datasets</Link>
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
        title={dataset.name}
        description={`${formatCaseCount(dataset.case_count)} · Version ${dataset.version}`}
        breadcrumbs={[{ label: "Datasets", href: "/datasets" }]}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => validateDataset.mutate(datasetId!)}
              disabled={validateDataset.isPending}
            >
              {validateDataset.isPending ? "Validating..." : "Validate"}
            </Button>
            <Button variant="secondary" size="sm" asChild>
              <Link to={`/datasets/${datasetId}/cases/new`}>Add Case</Link>
            </Button>
            <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
              <DialogTrigger asChild>
                <Button variant="ghost" size="sm" className="text-error">
                  <Trash2 className="h-4 w-4" />
                </Button>
              </DialogTrigger>
              <DialogPortal>
                <DialogOverlay />
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Delete dataset?</DialogTitle>
                    <DialogDescription>
                      <p>
                        <strong>{dataset.name}</strong> will be permanently removed.
                      </p>
                      <p className="mt-2">
                        Existing evaluation runs will remain available because they
                        contain immutable snapshots.
                      </p>
                    </DialogDescription>
                  </DialogHeader>
                  <DialogFooter>
                    <Button variant="secondary" onClick={() => setShowDeleteDialog(false)}>
                      Cancel
                    </Button>
                    <Button
                      variant="danger"
                      onClick={handleDelete}
                      disabled={deleteDataset.isPending}
                    >
                      {deleteDataset.isPending ? "Deleting..." : "Delete Dataset"}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </DialogPortal>
            </Dialog>
          </div>
        }
      />

      <Page.Content>
        <div className="space-y-6">
          {/* Metadata summary */}
          <Surface className="p-6">
            <h3 className="text-base font-medium text-text-primary">Dataset Information</h3>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <InfoRow label="Name" value={dataset.name} />
              <InfoRow label="Version" value={dataset.version} />
              <InfoRow label="Schema" value={dataset.schema_version} />
              <InfoRow label="Cases" value={formatCaseCount(dataset.case_count)} />
              <InfoRow label="Source" value={dataset.source ?? "—"} />
              <InfoRow label="Created" value={formatRelativeTime(dataset.created_at)} />
              <InfoRow label="Updated" value={formatRelativeTime(dataset.updated_at)} />
            </div>
            {dataset.tags.length > 0 && (
              <div className="mt-4">
                <p className="text-sm text-text-tertiary">Tags</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {dataset.tags.map((tag) => (
                    <Badge key={tag} variant="default">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </Surface>

          {/* Cases table */}
          <Surface>
            <div className="flex items-center justify-between p-4">
              <h3 className="text-base font-medium text-text-primary">Benchmark Cases</h3>
              <div className="w-64">
                <SearchInput
                  value={search}
                  onChange={(e) => handleSearch(e.target.value)}
                  placeholder="Search cases..."
                />
              </div>
            </div>

            {isLoadingCases ? (
              <div className="p-4">
                <Spinner />
              </div>
            ) : caseData && caseData.cases.length > 0 ? (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[80px]">ID</TableHead>
                      <TableHead>Query</TableHead>
                      <TableHead className="w-[120px]">Answerability</TableHead>
                      <TableHead className="w-[150px]">Tags</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {caseData.cases.map((caseSummary) => (
                      <CaseRow
                        key={caseSummary.case_id}
                        datasetId={datasetId!}
                        caseSummary={caseSummary}
                      />
                    ))}
                  </TableBody>
                </Table>

                {/* Pagination */}
                <div className="flex items-center justify-between border-t border-border p-4">
                  <p className="text-sm text-text-tertiary">
                    Showing {caseData.offset + 1}–{Math.min(caseData.offset + caseData.limit, caseData.total)} of{" "}
                    {caseData.total}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="primary"
                      size="sm"
                      disabled={page <= 1}
                      onClick={() => {
                        const newParams = new URLSearchParams(searchParams);
                        newParams.set("page", String(page - 1));
                        setSearchParams(newParams);
                      }}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      disabled={!caseData.has_more}
                      onClick={() => {
                        const newParams = new URLSearchParams(searchParams);
                        newParams.set("page", String(page + 1));
                        setSearchParams(newParams);
                      }}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              </>
            ) : (
              <div className="p-6">
                <EmptyState
                  title={search ? "No matching cases" : "No cases yet"}
                  description={
                    search
                      ? "Try adjusting your search."
                      : "Add cases to this dataset to begin building your benchmark."
                  }
                  action={
                    !search && (
                      <Button asChild>
                        <Link to={`/datasets/${datasetId}/cases/new`}>Add Case</Link>
                      </Button>
                    )
                  }
                />
              </div>
            )}
          </Surface>
        </div>
      </Page.Content>
    </Page>
  );
}

interface InfoRowProps {
  label: string;
  value: string;
}

function InfoRow({ label, value }: InfoRowProps) {
  return (
    <div>
      <p className="text-sm text-text-tertiary">{label}</p>
      <p className="mt-1 font-medium text-text-primary">{value}</p>
    </div>
  );
}

interface CaseRowProps {
  datasetId: string;
  caseSummary: { case_id: string; query: string; answerability: any; tags: string[] };
}

function CaseRow({ datasetId, caseSummary }: CaseRowProps) {
  return (
    <TableRow>
      <TableCell>
        <code className="text-xs text-text-secondary">{caseSummary.case_id}</code>
      </TableCell>
      <TableCell>
        <div className="max-w-xl truncate text-sm text-text-primary" title={caseSummary.query}>
          {truncateQuery(caseSummary.query, 80)}
        </div>
      </TableCell>
      <TableCell>
        <StatusBadge status={getAnswerabilityVariant(caseSummary.answerability)} showDot>
          {formatAnswerability(caseSummary.answerability)}
        </StatusBadge>
      </TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-1">
          {caseSummary.tags.slice(0, 2).map((tag) => (
            <Badge key={tag} variant="default" className="text-xs">
              {tag}
            </Badge>
          ))}
          {caseSummary.tags.length > 2 && (
            <span className="text-xs text-text-tertiary">
              +{caseSummary.tags.length - 2}
            </span>
          )}
        </div>
      </TableCell>
      <TableCell className="text-right">
        <Button variant="ghost" size="sm" asChild>
          <Link to={`/datasets/${datasetId}/cases/${caseSummary.case_id}`}>View</Link>
        </Button>
      </TableCell>
    </TableRow>
  );
}
