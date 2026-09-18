/**
 * Test detail page - shows test configuration and run history.
 */
import { useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import { EmptyState } from "@/components/ui/empty-state";
import { Spinner } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
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
import { MoreVertical, FlaskConical, Play, Trash2, Edit } from "lucide-react";
import { useTest, useTestRuns, useDeleteTest, useRunTest } from "../use-tests";
import { formatRunStatus, getRunStatusVariant, formatRelativeTime, formatExecutionConfig } from "../test-formatters";
import type { EvaluationRunSummary } from "../test-types";

export function TestDetailPage() {
  const { testId } = useParams<{ testId: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<"overview" | "runs">("overview");

  const { data: test, isLoading: testLoading, error: testError } = useTest(testId || "");
  const { data: runs, isLoading: runsLoading } = useTestRuns(testId || "");
  const deleteTest = useDeleteTest();
  const runTest = useRunTest();

  const handleDelete = async () => {
    if (!testId || !confirm("Are you sure you want to delete this test?")) return;

    try {
      await deleteTest.mutateAsync(testId);
      navigate("/tests");
    } catch (error) {
      console.error("Failed to delete test:", error);
    }
  };

  const handleRunAgain = async () => {
    if (!testId) return;

    try {
      const run = await runTest.mutateAsync({
        test_definition_id: testId,
        name: `${test?.name} - Run ${new Date().toLocaleDateString()}`,
      });

      navigate(`/runs/${run.run_id}`);
    } catch (error) {
      console.error("Failed to run test:", error);
    }
  };

  if (testLoading || runsLoading) {
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

  if (testError || !test) {
    return (
      <Page>
        <Page.Content>
          <Alert variant="error">
            <AlertDescription>
              Test not found or error loading test.
            </AlertDescription>
          </Alert>
        </Page.Content>
      </Page>
    );
  }

  return (
    <Page>
      <Page.Header
        title={test.name}
        description={test.description ?? "Test configuration and execution history."}
        breadcrumbs={[{ label: "Tests", href: "/tests" }]}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={handleRunAgain}>
              <Play className="mr-2 h-4 w-4" />
              Run Again
            </Button>
            <Button variant="secondary" asChild>
              <Link to={`/tests/${testId}/edit`}>
                <Edit className="mr-2 h-4 w-4" />
                Edit
              </Link>
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={handleDelete}>
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
          {/* Tabs */}
          <div className="flex border-b border-border">
            <button
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === "overview"
                  ? "border-b-2 border-accent text-accent-foreground"
                  : "text-text-tertiary hover:text-text-secondary"
              }`}
              onClick={() => setActiveTab("overview")}
            >
              Overview
            </button>
            <button
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === "runs"
                  ? "border-b-2 border-accent text-accent-foreground"
                  : "text-text-tertiary hover:text-text-secondary"
              }`}
              onClick={() => setActiveTab("runs")}
            >
              Runs ({runs?.length ?? 0})
            </button>
          </div>

          {activeTab === "overview" && (
            <div className="space-y-4">
              <Surface className="p-4">
                <h3 className="mb-3 text-sm font-medium text-text-primary">Configuration</h3>
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <div className="text-xs text-text-tertiary">Target</div>
                    <div className="font-medium text-text-primary">{test.target_id}</div>
                  </div>
                  <div>
                    <div className="text-xs text-text-tertiary">Dataset</div>
                    <div className="font-medium text-text-primary">{test.benchmark_id}</div>
                  </div>
                  <div>
                    <div className="text-xs text-text-tertiary">Metric Config</div>
                    <div className="font-medium text-text-primary">{test.metric_config_id}</div>
                  </div>
                  <div>
                    <div className="text-xs text-text-tertiary">Execution</div>
                    <div className="font-medium text-text-primary">
                      {formatExecutionConfig(test.execution_config)}
                    </div>
                  </div>
                </div>
              </Surface>

              <Surface className="p-4">
                <h3 className="mb-3 text-sm font-medium text-text-primary">Metadata</h3>
                <div className="grid gap-4 md:grid-cols-3">
                  <div>
                    <div className="text-xs text-text-tertiary">Created</div>
                    <div className="text-sm text-text-secondary">
                      {formatRelativeTime(test.created_at)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-text-tertiary">Updated</div>
                    <div className="text-sm text-text-secondary">
                      {formatRelativeTime(test.updated_at)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-text-tertiary">Tags</div>
                    <div className="flex flex-wrap gap-1">
                      {test.tags?.map((tag) => (
                        <span key={tag} className="rounded border border-border bg-surface px-1.5 py-0.5 text-xs text-text-tertiary">
                          {tag}
                        </span>
                      ))}
                      {(!test.tags || test.tags.length === 0) && (
                        <span className="text-sm text-text-tertiary">None</span>
                      )}
                    </div>
                  </div>
                </div>
              </Surface>
            </div>
          )}

          {activeTab === "runs" && (
            <Surface>
              {runs && runs.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Progress</TableHead>
                      <TableHead>Started</TableHead>
                      <TableHead>Finished</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {runs.map((run: EvaluationRunSummary) => (
                      <RunRow key={run.run_id} run={run} />
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <EmptyState
                  icon={<FlaskConical className="h-8 w-8" />}
                  title="No runs yet"
                  description="Run this test to see execution history here."
                  action={
                    <Button onClick={handleRunAgain}>
                      <Play className="mr-2 h-4 w-4" />
                      Run Test
                    </Button>
                  }
                />
              )}
            </Surface>
          )}
        </div>
      </Page.Content>
    </Page>
  );
}

interface RunRowProps {
  run: EvaluationRunSummary;
}

function RunRow({ run }: RunRowProps) {
  const progress = run.progress;

  return (
    <TableRow>
      <TableCell>
        <div>
          <div className="font-medium text-text-primary">{run.name}</div>
          <div className="text-xs text-text-tertiary">{run.run_id}</div>
        </div>
      </TableCell>
      <TableCell>
        <Badge variant={getRunStatusVariant(run.status)}>
          {formatRunStatus(run.status)}
        </Badge>
      </TableCell>
      <TableCell>
        {progress ? (
          <div className="text-sm text-text-secondary">
            {progress.complete_cases}/{progress.total_cases} ({progress.percent}%)
          </div>
        ) : (
          <span className="text-sm text-text-tertiary">-</span>
        )}
      </TableCell>
      <TableCell>
        <span className="text-sm text-text-tertiary">
          {run.started_at ? formatRelativeTime(run.started_at) : "-"}
        </span>
      </TableCell>
      <TableCell>
        <span className="text-sm text-text-tertiary">
          {run.finished_at ? formatRelativeTime(run.finished_at) : "-"}
        </span>
      </TableCell>
      <TableCell className="text-right">
        <Button variant="ghost" size="sm" asChild>
          <Link to={`/runs/${run.run_id}`}>View</Link>
        </Button>
      </TableCell>
    </TableRow>
  );
}
