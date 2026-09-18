/**
 * Active evaluations section for dashboard.
 *
 * Shows currently running evaluations with progress and status.
 */
import { Link } from "react-router-dom";
import { ProgressBar } from "@/components/ui/progress-bar";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import { formatRelativeTime, formatPercent } from "@/lib/format";
import type { DashboardRunSummary } from "./dashboard-types";

interface ActiveEvaluationsProps {
  activeRuns: DashboardRunSummary[];
}

export function ActiveEvaluations({ activeRuns }: ActiveEvaluationsProps) {
  if (activeRuns.length === 0) {
    return null;
  }

  // Emphasize the first (most recent) run
  const [primaryRun, ...otherRuns] = activeRuns;

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-medium text-text-primary">Active Evaluations</h2>
      </div>

      {/* Primary active run */}
      {primaryRun && (
        <Surface className="p-6">
          <div className="space-y-4">
            {/* Header */}
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <h3 className="text-lg font-semibold text-text-primary">
                  {primaryRun.testName}
                </h3>
                <p className="text-sm text-text-tertiary">
                  {primaryRun.targetName} · {primaryRun.datasetName}
                </p>
              </div>
              <StatusBadge status="info" showDot>
                Running
              </StatusBadge>
            </div>

            {/* Progress bar */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-text-secondary">
                  {primaryRun.progress.completed} / {primaryRun.progress.total} cases
                </span>
                <span className="font-medium text-text-primary">
                  {formatPercent(primaryRun.progress.percent / 100)} completed
                </span>
              </div>
              <ProgressBar value={primaryRun.progress.percent} className="h-2" />
            </div>

            {/* Metrics grid */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {primaryRun.metrics && (
                <>
                  <MetricStat label="Completed" value={primaryRun.metrics.completed} />
                  <MetricStat
                    label="Failed"
                    value={primaryRun.metrics.failed}
                    variant="error"
                  />
                  <MetricStat label="Remaining" value={primaryRun.metrics.remaining} />
                  {primaryRun.metrics.running && (
                    <MetricStat
                      label="Running"
                      value={primaryRun.metrics.running}
                      variant="info"
                    />
                  )}
                </>
              )}

              {/* Key metrics if available */}
              {primaryRun.keyMetrics?.map((metric) => (
                <MetricStat
                  key={metric.metricId}
                  label={metric.label}
                  value={
                    typeof metric.value === "number"
                      ? metric.value.toFixed(3)
                      : metric.value
                  }
                />
              ))}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between">
              <p className="text-sm text-text-tertiary">
                Started {formatRelativeTime(primaryRun.startedAt)}
              </p>
              <Button variant="secondary" size="sm" asChild>
                <Link to={`/runs/${primaryRun.runId}`}>View Run</Link>
              </Button>
            </div>
          </div>
        </Surface>
      )}

      {/* Additional active runs */}
      {otherRuns.length > 0 && (
        <div className="space-y-2">
          {otherRuns.map((run) => (
            <ActiveRunRow key={run.runId} run={run} />
          ))}
        </div>
      )}
    </section>
  );
}

interface MetricStatProps {
  label: string;
  value: string | number;
  variant?: "default" | "error" | "info";
}

function MetricStat({ label, value, variant = "default" }: MetricStatProps) {
  const variantStyles = {
    default: "text-text-primary",
    error: "text-error",
    info: "text-info",
  };

  return (
    <div>
      <p className="text-xs text-text-tertiary">{label}</p>
      <p className={`text-lg font-semibold ${variantStyles[variant]}`}>{value}</p>
    </div>
  );
}

interface ActiveRunRowProps {
  run: DashboardRunSummary;
}

function ActiveRunRow({ run }: ActiveRunRowProps) {
  return (
    <Link to={`/runs/${run.runId}`}>
      <Surface className="group p-4 transition-colors hover:bg-surface-hover">
        <div className="flex items-center justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <StatusBadge status="info" showDot>
                Running
              </StatusBadge>
              <p className="truncate font-medium text-text-primary">{run.testName}</p>
            </div>
            <p className="mt-1 text-sm text-text-tertiary">
              {run.targetName} · {run.datasetName}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-medium text-text-primary">
                {formatPercent(run.progress.percent / 100)}
              </p>
              <p className="text-xs text-text-tertiary">
                {formatRelativeTime(run.startedAt)}
              </p>
            </div>
            <ProgressBar
              value={run.progress.percent}
              className="hidden h-1.5 w-24 sm:block"
            />
          </div>
        </div>
      </Surface>
    </Link>
  );
}
