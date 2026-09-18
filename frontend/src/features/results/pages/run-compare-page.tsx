/**
 * Run comparison page - compares two evaluation runs.
 */
import { useParams, Link } from "react-router-dom";
import { Page } from "@/components/layout/page-layout";
import { Surface } from "@/components/layout/surface";
import { Spinner } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useRun, useRunComparison } from "../use-runs";
import {
  getRunStatusVariant,
  formatMetricValue,
  formatMetricDelta,
  getDeltaVariant,
} from "../run-formatters";

export function RunComparePage() {
  const { runId, otherRunId } = useParams<{ runId: string; otherRunId: string }>();

  const { data: runA, isLoading: runALoading } = useRun(runId || "");
  const { data: runB, isLoading: runBLoading } = useRun(otherRunId || "");
  const {
    data: comparison,
    isLoading: comparisonLoading,
    error: comparisonError,
  } = useRunComparison(runId || "", otherRunId || "");

  const isLoading = runALoading || runBLoading || comparisonLoading;

  if (isLoading) {
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

  if (comparisonError || !comparison) {
    return (
      <Page>
        <Page.Content>
          <Alert variant="error">
            <AlertDescription>
              Comparison not available or error loading comparison.
            </AlertDescription>
          </Alert>
        </Page.Content>
      </Page>
    );
  }

  return (
    <Page>
      <Page.Header
        title="Compare Runs"
        description="Compare metric performance between two evaluation runs."
        breadcrumbs={[
          { label: "Results", href: "/results" },
          { label: runA?.name ?? "Run A", href: `/runs/${String(runId)}` },
        ]}
      />

      <Page.Content>
        <div className="space-y-4">
          {/* Compatibility warnings */}
          {comparison.compatibility_warnings.length > 0 && (
            <Alert variant="warning">
              <AlertDescription>
                <ul className="list-inside list-disc">
                  {comparison.compatibility_warnings.map((warning, idx) => (
                    <li key={idx}>{warning}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          {/* Run identity */}
          <div className="grid gap-4 md:grid-cols-2">
            <Surface className="p-4">
              <h3 className="mb-2 text-sm font-medium text-text-primary">Run A</h3>
              <div className="space-y-2">
                <div className="font-medium text-text-primary">{runA?.name}</div>
                <StatusBadge status={getRunStatusVariant(runA?.status || "unknown")}>
                  {runA?.status}
                </StatusBadge>
                <div className="text-xs text-text-tertiary">{runA?.created_at}</div>
              </div>
            </Surface>

            <Surface className="p-4">
              <h3 className="mb-2 text-sm font-medium text-text-primary">Run B</h3>
              <div className="space-y-2">
                <div className="font-medium text-text-primary">{runB?.name}</div>
                <StatusBadge status={getRunStatusVariant(runB?.status || "unknown")}>
                  {runB?.status}
                </StatusBadge>
                <div className="text-xs text-text-tertiary">{runB?.created_at}</div>
              </div>
            </Surface>
          </div>

          {/* Metric comparison */}
          <Surface>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Metric</TableHead>
                  <TableHead>Aggregation</TableHead>
                  <TableHead className="text-right">Run A</TableHead>
                  <TableHead className="text-right">Run B</TableHead>
                  <TableHead className="text-right">Absolute Δ</TableHead>
                  <TableHead className="text-right">Relative Δ</TableHead>
                  <TableHead>Change</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {comparison.metric_comparisons.map((metricComp, idx) => {
                  const variant = getDeltaVariant(metricComp.absolute_delta);
                  return (
                    <TableRow key={idx}>
                      <TableCell>
                        <div>
                          <div className="font-medium text-text-primary">
                            {metricComp.metric_id}
                          </div>
                          <div className="text-xs text-text-tertiary">
                            v{metricComp.metric_version}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className="text-sm text-text-tertiary">
                          {metricComp.aggregation}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <span className="font-medium text-text-primary">
                          {formatMetricValue(
                            metricComp.run_a_value,
                            metricComp.metric_id
                          )}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <span className="font-medium text-text-primary">
                          {formatMetricValue(
                            metricComp.run_b_value,
                            metricComp.metric_id
                          )}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <span
                          className={`font-medium ${
                            variant === "success"
                              ? "text-success"
                              : variant === "error"
                                ? "text-error"
                                : "text-text-secondary"
                          }`}
                        >
                          {formatMetricDelta(
                            metricComp.absolute_delta,
                            metricComp.direction
                          )}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <span className="text-sm text-text-tertiary">
                          {metricComp.relative_delta_percent != null
                            ? `${metricComp.relative_delta_percent > 0 ? "+" : ""}${metricComp.relative_delta_percent.toFixed(1)}%`
                            : "—"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <StatusBadge
                          status={
                            metricComp.status === "improved"
                              ? "success"
                              : metricComp.status === "regressed"
                                ? "error"
                                : "neutral"
                          }
                        >
                          {metricComp.status}
                        </StatusBadge>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </Surface>

          {/* Summary */}
          <Surface className="p-4">
            <h3 className="mb-3 text-sm font-medium text-text-primary">Summary</h3>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <div className="text-xs text-text-tertiary">Improved</div>
                <div className="text-2xl font-semibold text-success">
                  {Number(comparison.summary.total_improved) || 0}
                </div>
              </div>
              <div>
                <div className="text-xs text-text-tertiary">Regressed</div>
                <div className="text-2xl font-semibold text-error">
                  {Number(comparison.summary.total_regressed) || 0}
                </div>
              </div>
              <div>
                <div className="text-xs text-text-tertiary">Unchanged</div>
                <div className="text-2xl font-semibold text-text-primary">
                  {Number(comparison.summary.total_unchanged) || 0}
                </div>
              </div>
            </div>
          </Surface>

          {/* Actions */}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" asChild>
              <Link to={`/runs/${String(runId)}`}>Back to Run A</Link>
            </Button>
            <Button variant="secondary" asChild>
              <Link to={`/runs/${String(otherRunId)}`}>Back to Run B</Link>
            </Button>
          </div>
        </div>
      </Page.Content>
    </Page>
  );
}
