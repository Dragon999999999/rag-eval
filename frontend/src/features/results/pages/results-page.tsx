/**
 * Results page - displays historical evaluation runs.
 */
import { useNavigate, useSearchParams } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import { Spinner } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { SearchInput } from "@/components/ui/search-input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FlaskConical } from "lucide-react";
import { useRunList } from "../use-runs";
import { useTargetList } from "@/features/targets/use-targets";
import {
  getRunStatusVariant,
  formatElapsedTime,
  formatRelativeTime,
} from "../run-formatters";
import type { RunSummary } from "../run-types";

export function ResultsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Read filters from URL
  const statusFilter = searchParams.get("status") ?? "";
  const testFilter = searchParams.get("test") ?? "";
  const targetFilter = searchParams.get("target") ?? "";
  const search = searchParams.get("search") ?? "";
  const page = parseInt(searchParams.get("page") ?? "1");

  const limit = 50;
  const offset = (page - 1) * limit;

  const {
    data: runs,
    isLoading,
    error,
    refetch,
  } = useRunList({
    status: statusFilter || undefined,
    test_definition_id: testFilter || undefined,
    target_id: targetFilter || undefined,
    search: search || undefined,
    limit,
    offset,
  });
  const { data: targets } = useTargetList({ autoHealthCheck: false });
  const targetNames = new Map(
    (targets ?? []).map((target) => [target.target_id, target.name])
  );
  const displayRuns = runs ?? [];

  const handleStatusChange = (value: string) => {
    const newParams = new URLSearchParams(searchParams);
    if (value && value !== "all") {
      newParams.set("status", value);
    } else {
      newParams.delete("status");
    }
    newParams.set("page", "1"); // Reset to first page
    setSearchParams(newParams);
  };

  const handleSearchChange = (value: string) => {
    const newParams = new URLSearchParams(searchParams);
    if (value) {
      newParams.set("search", value);
    } else {
      newParams.delete("search");
    }
    newParams.set("page", "1");
    setSearchParams(newParams);
  };

  const handlePageChange = (newPage: number) => {
    const newParams = new URLSearchParams(searchParams);
    newParams.set("page", newPage.toString());
    setSearchParams(newParams);
  };

  if (isLoading) {
    return (
      <Page>
        <Page.Header
          title="Results"
          description="Inspect completed evaluations and compare system performance."
        />
        <Page.Content>
          <div className="flex items-center justify-center py-12">
            <Spinner size="lg" />
          </div>
        </Page.Content>
      </Page>
    );
  }

  if (error) {
    return (
      <Page>
        <Page.Header
          title="Results"
          description="Inspect completed evaluations and compare system performance."
        />
        <Page.Content>
          <Alert variant="error">
            <AlertDescription>
              An error occurred while fetching results.
              <Button
                variant="secondary"
                size="sm"
                onClick={() => void refetch()}
                className="ml-4"
              >
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        </Page.Content>
      </Page>
    );
  }

  return (
    <Page>
      <Page.Header
        title="Results"
        description="Inspect completed evaluations and compare system performance."
      />

      <Page.Content>
        <div className="space-y-4">
          {/* Filters */}
          <div className="flex items-center gap-4">
            <div className="w-64">
              <SearchInput
                value={search}
                onChange={(e) => {
                  handleSearchChange(e.target.value);
                }}
                placeholder="Search runs..."
              />
            </div>

            <Select value={statusFilter} onValueChange={handleStatusChange}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="All Statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="RUNNING">Running</SelectItem>
                <SelectItem value="COMPLETE">Completed</SelectItem>
                <SelectItem value="COMPLETED_WITH_ERRORS">
                  Completed with errors
                </SelectItem>
                <SelectItem value="FAILED">Failed</SelectItem>
                <SelectItem value="CANCELLED">Cancelled</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Results table */}
          <Surface>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Test</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead>Dataset</TableHead>
                  <TableHead className="w-[120px]">Status</TableHead>
                  <TableHead className="w-[150px]">Key Result</TableHead>
                  <TableHead className="w-[120px]">Duration</TableHead>
                  <TableHead className="w-[150px]">Started</TableHead>
                  <TableHead className="w-[100px] text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {displayRuns.length > 0 ? (
                  displayRuns.map((run: RunSummary) => (
                    <RunRow
                      key={run.run_id}
                      run={run}
                      targetName={
                        run.target_id ? targetNames.get(run.target_id) : undefined
                      }
                    />
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={8} className="py-12 text-center">
                      <div className="space-y-3">
                        <FlaskConical className="mx-auto h-8 w-8 text-text-tertiary" />
                        <div>
                          <p className="font-medium text-text-primary">
                            No evaluation results found
                          </p>
                          <p className="text-sm text-text-tertiary">
                            Try another filter or create a test to start a run.
                          </p>
                        </div>
                        <Button
                          size="sm"
                          onClick={() => {
                            navigate("/tests/new");
                          }}
                        >
                          Create Test
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Surface>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-text-tertiary">
              {displayRuns.length > 0
                ? `Showing ${String(offset + 1)}-${String(offset + displayRuns.length)} runs`
                : "Showing 0 runs"}
            </div>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={page <= 1}
                onClick={() => {
                  handlePageChange(page - 1);
                }}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={displayRuns.length < limit}
                onClick={() => {
                  handlePageChange(page + 1);
                }}
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      </Page.Content>
    </Page>
  );
}

interface RunRowProps {
  run: RunSummary;
  targetName?: string;
}

function RunRow({ run, targetName }: RunRowProps) {
  const navigate = useNavigate();
  const started = run.started_at ? new Date(run.started_at).getTime() : Date.now();
  const finished = run.finished_at ? new Date(run.finished_at).getTime() : Date.now();
  const duration = run.finished_at ? (finished - started) / 1000 : null;

  // Get a representative metric value
  const keyResult =
    ["COMPLETE", "COMPLETED", "COMPLETED_WITH_ERRORS"].includes(run.status) &&
    run.progress_percent !== undefined
      ? `${run.progress_percent.toFixed(0)}% complete`
      : "—";

  return (
    <TableRow
      className="cursor-pointer transition-colors hover:bg-surface-hover"
      onClick={() => {
        navigate(`/runs/${encodeURIComponent(run.run_id)}`);
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          navigate(`/runs/${encodeURIComponent(run.run_id)}`);
        }
      }}
      tabIndex={0}
    >
      <TableCell>
        <div>
          <div className="font-medium text-text-primary">{run.name}</div>
          {run.test_definition_id && (
            <div className="text-xs text-text-tertiary">{run.test_definition_id}</div>
          )}
        </div>
      </TableCell>
      <TableCell>
        <div>
          <div className="font-medium text-text-primary">{targetName ?? "—"}</div>
          {run.target_id && (
            <div className="text-xs text-text-tertiary">{run.target_id}</div>
          )}
        </div>
      </TableCell>
      <TableCell>
        <div className="text-sm text-text-secondary">Dataset</div>
      </TableCell>
      <TableCell>
        <StatusBadge status={getRunStatusVariant(run.status)} showDot>
          {run.status}
        </StatusBadge>
      </TableCell>
      <TableCell>
        <div className="text-sm text-text-secondary">{keyResult}</div>
      </TableCell>
      <TableCell>
        <div className="text-sm text-text-tertiary">{formatElapsedTime(duration)}</div>
      </TableCell>
      <TableCell>
        <div className="text-sm text-text-tertiary">
          {formatRelativeTime(run.started_at)}
        </div>
      </TableCell>
      <TableCell className="text-right">
        <Button variant="ghost" size="sm">
          View
        </Button>
      </TableCell>
    </TableRow>
  );
}
