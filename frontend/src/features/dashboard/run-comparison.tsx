/**
 * Run comparison section for dashboard.
 *
 * Shows comparison between latest run and previous baseline.
 */
import { Link } from "react-router-dom";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import { formatDelta } from "@/lib/format";
import type { RunComparisonSummary } from "./dashboard-types";

interface RunComparisonProps {
  comparison: RunComparisonSummary;
}

export function RunComparison({ comparison }: RunComparisonProps) {
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-medium text-text-primary">
          Compared with Previous Run
        </h2>
        <Button variant="secondary" size="sm" asChild>
          <Link to="/results">Open Comparison</Link>
        </Button>
      </div>

      <Surface className="p-6">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <p className="text-sm text-text-secondary">
              <span className="font-medium">{comparison.comparisonName}</span> vs{" "}
              <span className="font-medium">{comparison.baselineName}</span>
            </p>
            <p className="text-xs text-text-tertiary">
              {new Date(comparison.comparedAt).toLocaleString()}
            </p>
          </div>
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Metric</TableHead>
              <TableHead className="w-[120px] text-right">Previous</TableHead>
              <TableHead className="w-[120px] text-right">Current</TableHead>
              <TableHead className="w-[120px] text-right">Change</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {comparison.metrics.map((metric) => {
              const deltaInfo = formatDelta(
                metric.absoluteDelta ?? 0,
                metric.direction,
                metric.unit
              );

              const deltaStyle = deltaInfo.isImprovement
                ? "text-success"
                : deltaInfo.isNeutral
                  ? "text-text-tertiary"
                  : "text-error";

              return (
                <TableRow key={metric.metricId}>
                  <TableCell className="font-medium text-text-primary">
                    {metric.label}
                  </TableCell>
                  <TableCell className="text-right text-text-secondary">
                    {metric.previousValue !== null
                      ? formatValue(metric.previousValue, metric.unit)
                      : "—"}
                  </TableCell>
                  <TableCell className="text-right font-medium text-text-primary">
                    {metric.currentValue !== null
                      ? formatValue(metric.currentValue, metric.unit)
                      : "—"}
                  </TableCell>
                  <TableCell className={`text-right font-medium ${deltaStyle}`}>
                    {metric.absoluteDelta !== null ? deltaInfo.text : "—"}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Surface>
    </section>
  );
}

function formatValue(value: number, unit?: string): string {
  if (unit === "ms") {
    return `${Math.round(value).toString()}${unit}`;
  }
  return value.toFixed(3);
}
