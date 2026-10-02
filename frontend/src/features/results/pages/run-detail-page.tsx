/**
 * Run detail page - shows evaluation run status, progress, and results.
 */
import { Fragment, useMemo, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import { EmptyState } from "@/components/ui/empty-state";
import { Spinner } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ProgressBar } from "@/components/ui/progress-bar";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreVertical, Pause, Download, GitCompare, Trash2 } from "lucide-react";
import type { AggregateResultDetail, CaseExecutionSummary } from "../run-types";
import { MetricResultsMatrix } from "../components/metric-results-matrix";
import {
  useRun,
  useRunProgress,
  useRunResults,
  useRunCases,
  useCancelRun,
} from "../use-runs";
import {
  getRunStatusVariant,
  formatRunStatus,
  formatElapsedTime,
  formatRelativeTime,
  formatMetricValue,
  formatMetricStatus,
  formatMetricStatistic,
  getMetricCatalogEntry,
  getMetricStatistics,
  isMetricStatisticAllowed,
} from "../run-formatters";

interface KeyMetricRow {
  metricId: string;
  metricVersion: string;
  family: string;
  label: string;
  values: Map<string, AggregateResultDetail>;
}

function groupKeyMetrics(aggregates: AggregateResultDetail[]): KeyMetricRow[] {
  const rows = new Map<string, KeyMetricRow>();

  for (const aggregate of aggregates) {
    const statistic = aggregate.aggregation.toLowerCase();
    if (!isMetricStatisticAllowed(aggregate.metric_id, statistic)) continue;

    const key = `${aggregate.metric_id}:${aggregate.metric_version}`;
    const entry = getMetricCatalogEntry(aggregate.metric_id);
    const row = rows.get(key) ?? {
      metricId: aggregate.metric_id,
      metricVersion: aggregate.metric_version,
      family: entry.family,
      label: entry.label,
      values: new Map<string, AggregateResultDetail>(),
    };
    row.values.set(statistic, aggregate);
    rows.set(key, row);
  }

  return [...rows.values()].sort(
    (left, right) =>
      left.family.localeCompare(right.family) || left.label.localeCompare(right.label)
  );
}

export function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<"overview" | "cases" | "metrics">(
    "metrics"
  );

  const { data: run, isLoading: runLoading, error: runError } = useRun(runId || "");
  const { data: progress, isLoading: progressLoading } = useRunProgress(runId || "", {
    refetchInterval:
      run && ["PENDING", "RUNNING", "PAUSING"].includes(run.status) ? 3000 : false,
  });
  const {
    data: results,
    isLoading: resultsLoading,
    error: resultsError,
  } = useRunResults(runId || "");
  const { data: casesData, isLoading: casesLoading } = useRunCases(runId || "");
  const cancelRun = useCancelRun();

  const handleCancel = async () => {
    if (!runId || !confirm("Cancel evaluation? This will stop all running cases."))
      return;

    try {
      await cancelRun.mutateAsync(runId);
      navigate("/results");
    } catch (error) {
      console.error("Failed to cancel run:", error);
    }
  };

  const aggregates = useMemo(() => results?.aggregates ?? [], [results?.aggregates]);
  const keyMetricRows = useMemo(() => groupKeyMetrics(aggregates), [aggregates]);
  const keyMetricStatistics = useMemo(
    () => getMetricStatistics(keyMetricRows.map((row) => row.metricId)),
    [keyMetricRows]
  );
  const keyMetricGroups = useMemo(() => {
    const groups = new Map<string, KeyMetricRow[]>();
    for (const row of keyMetricRows) {
      groups.set(row.family, [...(groups.get(row.family) ?? []), row]);
    }
    return [...groups.entries()];
  }, [keyMetricRows]);

  if (runLoading || progressLoading) {
    return (
      <Page>
        <Page.Content>
          <div className="flex items-center justify-center py-12">
            <Spinner size="lg" />
          </div>
        </Page.Content>
      </Page>
    );
  }

  if (runError || !run) {
    return (
      <Page>
        <Page.Content>
          <Alert variant="error">
            <AlertDescription>Run not found or error loading run.</AlertDescription>
          </Alert>
        </Page.Content>
      </Page>
    );
  }

  const isRunning = ["PENDING", "RUNNING", "PAUSING", "PAUSED"].includes(run.status);
  const isCompleted = ["COMPLETE", "COMPLETED_WITH_ERRORS", "completed"].includes(
    run.status
  );

  return (
    <Page>
      <Page.Header
        title={run.name}
        description={`${formatRunStatus(run.status)} · ${formatRelativeTime(run.created_at)}`}
        breadcrumbs={[{ label: "Results", href: "/results" }]}
        actions={
          <div className="flex gap-2">
            {isRunning && (
              <Button variant="secondary" onClick={() => void handleCancel()}>
                <Pause className="mr-2 h-4 w-4" />
                Cancel Run
              </Button>
            )}
            {isCompleted && (
              <>
                <Button variant="secondary">
                  <GitCompare className="mr-2 h-4 w-4" />
                  Compare
                </Button>
                <Button variant="secondary">
                  <Download className="mr-2 h-4 w-4" />
                  Export
                </Button>
              </>
            )}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem>
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        }
      />

      <Page.Content>
        <div className="space-y-6">
          {/* Progress section for running runs */}
          {isRunning && progress && (
            <Surface className="p-6">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <StatusBadge status={getRunStatusVariant(run.status)} showDot>
                      {run.status}
                    </StatusBadge>
                    <span className="text-sm text-text-tertiary">
                      {formatElapsedTime(progress.elapsed_seconds)} elapsed
                    </span>
                  </div>
                  <span className="text-lg font-semibold text-text-primary">
                    {progress.progress_percent}%
                  </span>
                </div>

                <ProgressBar value={progress.progress_percent} className="h-3" />

                <div className="grid grid-cols-4 gap-4">
                  <div>
                    <div className="text-xs text-text-tertiary">Completed</div>
                    <div className="text-lg font-semibold text-success">
                      {progress.complete_cases}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-text-tertiary">Failed</div>
                    <div className="text-lg font-semibold text-error">
                      {progress.failed_cases}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-text-tertiary">Running</div>
                    <div className="text-lg font-semibold text-info">
                      {progress.running_cases}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-text-tertiary">Total</div>
                    <div className="text-lg font-semibold text-text-primary">
                      {progress.total_cases}
                    </div>
                  </div>
                </div>
              </div>
            </Surface>
          )}

          {/* Aggregate metrics for completed runs */}
          {keyMetricGroups.length > 0 && (
            <Surface className="p-6">
              <div className="mb-4">
                <h3 className="text-sm font-medium text-text-primary">Key Metrics</h3>
                <p className="mt-1 text-xs text-text-tertiary">
                  Statistics are shown only where they are meaningful for the metric.
                </p>
              </div>
              <div className="overflow-x-auto">
                <Table className="min-w-max">
                  <TableHeader>
                    <TableRow>
                      <TableHead className="min-w-[230px]">Metric</TableHead>
                      {keyMetricStatistics.map((statistic) => (
                        <TableHead key={statistic} className="text-right">
                          {formatMetricStatistic(statistic)}
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {keyMetricGroups.map(([family, rows]) => (
                      <Fragment key={family}>
                        <TableRow className="bg-surface-elevated">
                          <TableCell
                            colSpan={keyMetricStatistics.length + 1}
                            className="py-2 text-xs font-medium uppercase tracking-wide text-text-tertiary"
                          >
                            {family}
                          </TableCell>
                        </TableRow>
                        {rows.map((row) => (
                          <TableRow key={`${row.metricId}:${row.metricVersion}`}>
                            <TableCell>
                              <div className="font-medium text-text-primary">
                                {row.family} · {row.label}
                              </div>
                              <div className="font-mono text-[10px] text-text-tertiary">
                                v{row.metricVersion}
                              </div>
                            </TableCell>
                            {keyMetricStatistics.map((statistic) => {
                              const aggregate = row.values.get(statistic);
                              const isComputed =
                                aggregate?.status.toUpperCase() === "COMPUTED";
                              return (
                                <TableCell
                                  key={statistic}
                                  className="whitespace-nowrap text-right text-sm"
                                >
                                  {aggregate
                                    ? isComputed
                                      ? formatMetricValue(
                                          aggregate.value,
                                          row.metricId,
                                          statistic
                                        )
                                      : formatMetricStatus(aggregate.status)
                                    : "—"}
                                </TableCell>
                              );
                            })}
                          </TableRow>
                        ))}
                      </Fragment>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </Surface>
          )}

          {/* Tabs */}
          <div className="border-border flex border-b">
            <button
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === "overview"
                  ? "text-accent-foreground border-b-2 border-accent"
                  : "text-text-tertiary hover:text-text-secondary"
              }`}
              onClick={() => {
                setActiveTab("overview");
              }}
            >
              Overview
            </button>
            <button
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === "cases"
                  ? "text-accent-foreground border-b-2 border-accent"
                  : "text-text-tertiary hover:text-text-secondary"
              }`}
              onClick={() => {
                setActiveTab("cases");
              }}
            >
              Cases
            </button>
            <button
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === "metrics"
                  ? "text-accent-foreground border-b-2 border-accent"
                  : "text-text-tertiary hover:text-text-secondary"
              }`}
              onClick={() => {
                setActiveTab("metrics");
              }}
            >
              Metrics
            </button>
          </div>

          {activeTab === "overview" && (
            <div className="space-y-4">
              <Surface className="p-4">
                <h3 className="mb-3 text-sm font-medium text-text-primary">
                  Configuration
                </h3>
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <div className="text-xs text-text-tertiary">Target</div>
                    <div className="font-medium text-text-primary">
                      {run.target_id ?? "—"}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-text-tertiary">Test Definition</div>
                    <div className="font-medium text-text-primary">
                      {run.test_definition_id ? (
                        <Link
                          to={`/tests/${run.test_definition_id}`}
                          className="text-accent hover:underline"
                        >
                          {run.test_definition_id}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-text-tertiary">Config Hash</div>
                    <div className="font-mono text-xs text-text-secondary">
                      {run.config_hash}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-text-tertiary">RAG-Eval Version</div>
                    <div className="font-medium text-text-primary">
                      {run.rag_eval_version ?? "—"}
                    </div>
                  </div>
                </div>
              </Surface>

              <Surface className="p-4">
                <h3 className="mb-3 text-sm font-medium text-text-primary">Timeline</h3>
                <div className="grid gap-4 md:grid-cols-3">
                  <div>
                    <div className="text-xs text-text-tertiary">Created</div>
                    <div className="text-sm text-text-secondary">
                      {formatRelativeTime(run.created_at)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-text-tertiary">Started</div>
                    <div className="text-sm text-text-secondary">
                      {formatRelativeTime(run.started_at)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-text-tertiary">Finished</div>
                    <div className="text-sm text-text-secondary">
                      {formatRelativeTime(run.finished_at)}
                    </div>
                  </div>
                </div>
              </Surface>
            </div>
          )}

          {activeTab === "cases" && (
            <Surface>
              {casesData && casesData.cases.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Case</TableHead>
                      <TableHead>Query</TableHead>
                      <TableHead className="w-[120px]">Status</TableHead>
                      <TableHead className="w-[150px]">Duration</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {casesData.cases.map((caseExec: CaseExecutionSummary) => (
                      <TableRow key={caseExec.case_execution_id}>
                        <TableCell>
                          <div className="font-mono text-xs">{caseExec.case_id}</div>
                        </TableCell>
                        <TableCell>
                          <div className="max-w-md truncate text-sm text-text-secondary">
                            {caseExec.status}
                          </div>
                        </TableCell>
                        <TableCell>
                          <StatusBadge
                            status={
                              caseExec.status === "COMPLETE"
                                ? "success"
                                : caseExec.status === "FAILED"
                                  ? "error"
                                  : "neutral"
                            }
                          >
                            {caseExec.status}
                          </StatusBadge>
                        </TableCell>
                        <TableCell>
                          <div className="text-sm text-text-tertiary">
                            {caseExec.started_at && caseExec.finished_at
                              ? formatElapsedTime(
                                  (new Date(caseExec.finished_at).getTime() -
                                    new Date(caseExec.started_at).getTime()) /
                                    1000
                                )
                              : "—"}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="sm" asChild>
                            <Link
                              to={`/runs/${String(runId)}/cases/${caseExec.case_id}`}
                            >
                              View
                            </Link>
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <EmptyState
                  title="No cases"
                  description="No case executions found for this run."
                />
              )}
            </Surface>
          )}

          {activeTab === "metrics" && (
            <Surface className="p-4">
              <h3 className="mb-4 text-sm font-medium text-text-primary">
                Metric Results
              </h3>
              {resultsLoading || casesLoading ? (
                <div className="flex justify-center py-10">
                  <Spinner />
                </div>
              ) : resultsError ? (
                <Alert variant="error">
                  <AlertDescription>
                    Metric results could not be loaded.
                  </AlertDescription>
                </Alert>
              ) : (
                <MetricResultsMatrix
                  runId={runId || ""}
                  cases={casesData?.cases ?? []}
                  metrics={results?.metrics ?? []}
                  aggregates={aggregates}
                />
              )}
            </Surface>
          )}
        </div>
      </Page.Content>
    </Page>
  );
}
