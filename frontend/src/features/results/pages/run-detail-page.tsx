/**
 * Run detail page - shows evaluation run status, progress, and results.
 */
import { useState } from "react";
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
import type { AggregateResultSummary, CaseExecutionSummary } from "../run-types";
import {
  useRun,
  useRunProgress,
  useRunAggregates,
  useRunCases,
  useCancelRun,
} from "../use-runs";
import {
  getRunStatusVariant,
  formatRunStatus,
  formatElapsedTime,
  formatRelativeTime,
  formatMetricValue,
} from "../run-formatters";

export function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<"overview" | "cases" | "metrics">(
    "overview"
  );

  const { data: run, isLoading: runLoading, error: runError } = useRun(runId || "");
  const { data: progress, isLoading: progressLoading } = useRunProgress(runId || "", {
    refetchInterval: run?.status === "running" ? 3000 : false,
  });
  const { data: aggregates } = useRunAggregates(runId || "");
  const { data: casesData } = useRunCases(runId || "", { limit: 10 });
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

  const isRunning = run.status === "running" || run.status === "queued";
  const isCompleted = run.status === "completed";

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
          {isCompleted && aggregates && aggregates.length > 0 && (
            <Surface className="p-6">
              <h3 className="mb-4 text-sm font-medium text-text-primary">
                Key Metrics
              </h3>
              <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
                {aggregates.map((agg: AggregateResultSummary) => (
                  <div key={agg.metric_id} className="space-y-1">
                    <div className="text-xs text-text-tertiary">
                      {agg.metric_id.split(".").pop()}
                    </div>
                    <div className="text-lg font-semibold text-text-primary">
                      {formatMetricValue(agg.value_summary, agg.metric_id)}
                    </div>
                  </div>
                ))}
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
              onClick={() => setActiveTab("overview")}
            >
              Overview
            </button>
            <button
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === "cases"
                  ? "text-accent-foreground border-b-2 border-accent"
                  : "text-text-tertiary hover:text-text-secondary"
              }`}
              onClick={() => setActiveTab("cases")}
            >
              Cases
            </button>
            <button
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === "metrics"
                  ? "text-accent-foreground border-b-2 border-accent"
                  : "text-text-tertiary hover:text-text-secondary"
              }`}
              onClick={() => setActiveTab("metrics")}
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
                              caseExec.status === "completed"
                                ? "success"
                                : caseExec.status === "failed"
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
                              to={`/runs/${String(runId)}/cases/${String(caseExec.case_id)}`}
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
              {aggregates && aggregates.length > 0 ? (
                <div className="space-y-4">
                  {aggregates.map((agg: AggregateResultSummary) => (
                    <div
                      key={agg.metric_id}
                      className="border-border flex items-center justify-between border-b pb-3"
                    >
                      <div>
                        <div className="font-medium text-text-primary">
                          {agg.metric_id}
                        </div>
                        <div className="text-xs text-text-tertiary">
                          v{agg.metric_version} · {agg.aggregation}
                        </div>
                      </div>
                      <div className="text-lg font-semibold text-text-primary">
                        {formatMetricValue(agg.value_summary, agg.metric_id)}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="No metrics"
                  description="No metric results available for this run."
                />
              )}
            </Surface>
          )}
        </div>
      </Page.Content>
    </Page>
  );
}
