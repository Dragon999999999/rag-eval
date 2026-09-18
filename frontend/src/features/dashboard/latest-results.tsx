/**
 * Latest results section for dashboard.
 *
 * Shows the most recent completed evaluation with key metrics.
 */
import { Link } from "react-router-dom";
import { MetricCard } from "@/components/ui/metric-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import { formatDuration, formatRelativeTime, formatDelta } from "@/lib/format";
import type { LatestRunSummary } from "./dashboard-types";

interface LatestResultsProps {
  latestRun: LatestRunSummary;
}

export function LatestResults({ latestRun }: LatestResultsProps) {
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-medium text-text-primary">Latest Results</h2>
        <Button variant="secondary" size="sm" asChild>
          <Link to={`/runs/${latestRun.runId}`}>View Run</Link>
        </Button>
      </div>

      <Surface className="p-6">
        {/* Header */}
        <div className="mb-6 flex items-start justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold text-text-primary">
                {latestRun.testName}
              </h3>
              <StatusBadge
                status={latestRun.status === "completed" ? "success" : "error"}
                showDot
              >
                {latestRun.status}
              </StatusBadge>
            </div>
            <p className="text-sm text-text-tertiary">
              {latestRun.targetName} · {latestRun.datasetName}
            </p>
            <p className="text-xs text-text-tertiary">
              {formatRelativeTime(latestRun.startedAt)} ·{" "}
              {formatDuration(latestRun.duration)}
            </p>
          </div>
        </div>

        {/* Metrics grid */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {latestRun.metrics.map((metric) => {
            const deltaInfo = metric.delta
              ? formatDelta(metric.delta.value, metric.delta.direction, metric.unit)
              : undefined;

            return (
              <MetricCard
                key={metric.metricId}
                label={metric.label}
                value={
                  typeof metric.value === "number"
                    ? metric.unit === "ms"
                      ? Math.round(metric.value)
                      : metric.value.toFixed(3)
                    : metric.value
                }
                trend={
                  deltaInfo
                    ? {
                        value: deltaInfo.text,
                        direction: deltaInfo.isImprovement
                          ? "up"
                          : deltaInfo.isNeutral
                            ? "neutral"
                            : "down",
                      }
                    : undefined
                }
              />
            );
          })}
        </div>
      </Surface>
    </section>
  );
}
