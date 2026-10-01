import { useMemo } from "react";
import { ChevronRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils/cn";
import { formatMetricStatus, formatMetricValue } from "../run-formatters";
import type {
  AggregateResultDetail,
  CaseExecutionSummary,
  MetricResultDetail,
} from "../run-types";

interface MetricColumn {
  key: string;
  metricId: string;
  version: string;
}

interface MetricResultsMatrixProps {
  runId: string;
  cases: CaseExecutionSummary[];
  metrics: MetricResultDetail[];
  aggregates: AggregateResultDetail[];
}

type Statistic = "computed" | "mean" | "median" | "min" | "max";

function metricLabel(metricId: string): string {
  return (metricId.split(".").at(-1) ?? metricId)
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function metricFamily(metricId: string): string {
  return metricId.split(".")[0] ?? "other";
}

function statusVariant(
  status: string
): "default" | "success" | "warning" | "error" | "info" {
  switch (status.toUpperCase()) {
    case "COMPUTED":
      return "success";
    case "FAILED":
      return "error";
    case "UNAVAILABLE_MISSING_INPUT":
    case "NOT_APPLICABLE":
    case "SKIPPED":
      return "warning";
    default:
      return "default";
  }
}

function numericValues(column: MetricColumn, metrics: MetricResultDetail[]): number[] {
  return metrics
    .filter(
      (item) =>
        item.metric_id === column.metricId &&
        item.metric_version === column.version &&
        item.status.toUpperCase() === "COMPUTED" &&
        typeof item.value === "number"
    )
    .map((item) => item.value as number);
}

function statisticValue(
  statistic: Statistic,
  column: MetricColumn,
  metrics: MetricResultDetail[]
): number | null {
  const values = numericValues(column, metrics).sort((a, b) => a - b);
  if (statistic === "computed") {
    return metrics.filter(
      (item) =>
        item.metric_id === column.metricId &&
        item.metric_version === column.version &&
        item.status.toUpperCase() === "COMPUTED"
    ).length;
  }
  if (values.length === 0) return null;
  if (statistic === "mean") {
    return values.reduce((sum, value) => sum + value, 0) / values.length;
  }
  if (statistic === "min") return values[0] ?? null;
  if (statistic === "max") return values.at(-1) ?? null;
  const middle = Math.floor(values.length / 2);
  return values.length % 2 === 0
    ? ((values[middle - 1] ?? 0) + (values[middle] ?? 0)) / 2
    : (values[middle] ?? null);
}

function cellFor(
  caseItem: CaseExecutionSummary,
  column: MetricColumn,
  metrics: MetricResultDetail[]
): MetricResultDetail | undefined {
  return metrics.find(
    (item) =>
      (item.case_id === caseItem.case_id ||
        item.case_execution_id === caseItem.case_execution_id) &&
      item.metric_id === column.metricId &&
      item.metric_version === column.version
  );
}

function CellValue({
  result,
  metricId,
}: {
  result: MetricResultDetail | undefined;
  metricId: string;
}) {
  if (!result) return <span className="text-text-tertiary">Pending</span>;

  const status = result.status.toUpperCase();
  const isComputed = status === "COMPUTED";
  const displayValue = isComputed
    ? formatMetricValue(result.value, metricId)
    : formatMetricStatus(result.status);

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex max-w-[150px] cursor-help items-center gap-1">
          {!isComputed && <span className="h-1.5 w-1.5 rounded-full bg-warning" />}
          <span className={cn(!isComputed && "text-text-tertiary")}>
            {displayValue}
          </span>
        </span>
      </TooltipTrigger>
      <TooltipContent>
        <div className="max-w-xs space-y-1">
          <div className="font-medium">{formatMetricStatus(result.status)}</div>
          {result.reason && <div>{result.reason}</div>}
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

function StatisticRow({
  statistic,
  columns,
  metrics,
  bottom = false,
}: {
  statistic: Statistic;
  columns: MetricColumn[];
  metrics: MetricResultDetail[];
  bottom?: boolean;
}) {
  const label =
    statistic === "computed"
      ? "Computed"
      : statistic.charAt(0).toUpperCase() + statistic.slice(1);
  return (
    <TableRow className={cn("bg-surface-elevated", bottom && "border-t-2")}>
      <TableCell className="sticky left-0 z-20 whitespace-nowrap bg-surface-elevated font-medium">
        {label}
      </TableCell>
      {columns.map((column) => {
        const value = statisticValue(statistic, column, metrics);
        return (
          <TableCell key={column.key} className="whitespace-nowrap text-right text-xs">
            {value === null
              ? "—"
              : statistic === "computed"
                ? value
                : formatMetricValue(value, column.metricId)}
          </TableCell>
        );
      })}
    </TableRow>
  );
}

export function MetricResultsMatrix({
  runId,
  cases,
  metrics,
  aggregates,
}: MetricResultsMatrixProps) {
  const navigate = useNavigate();
  const columns = useMemo<MetricColumn[]>(() => {
    const seen = new Set<string>();
    return metrics.reduce<MetricColumn[]>((result, item) => {
      const key = `${item.metric_id}:${item.metric_version}`;
      if (!seen.has(key)) {
        seen.add(key);
        result.push({ key, metricId: item.metric_id, version: item.metric_version });
      }
      return result;
    }, []);
  }, [metrics]);
  const families = useMemo(() => {
    const grouped = new Map<string, MetricColumn[]>();
    for (const column of columns) {
      const family = metricFamily(column.metricId);
      grouped.set(family, [...(grouped.get(family) ?? []), column]);
    }
    return [...grouped.entries()];
  }, [columns]);

  if (cases.length === 0) {
    return (
      <div className="p-8 text-center text-sm text-text-tertiary">
        No cases in this run.
      </div>
    );
  }
  if (columns.length === 0) {
    return (
      <div className="p-8 text-center text-sm text-text-tertiary">
        No metric results have been persisted yet. Cases will appear here as they
        complete.
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={250}>
      <div className="max-h-[min(70vh,720px)] overflow-auto">
        <Table className="min-w-max border-separate border-spacing-0">
          <TableHeader>
            <TableRow className="bg-surface-elevated">
              <TableHead className="sticky left-0 top-0 z-30 min-w-[220px] bg-surface-elevated">
                Case
              </TableHead>
              {families.map(([family, familyColumns]) => (
                <TableHead
                  key={family}
                  colSpan={familyColumns.length}
                  className="sticky top-0 z-20 border-l border-border-default bg-surface-elevated text-center text-xs uppercase tracking-wide"
                >
                  {family}
                </TableHead>
              ))}
            </TableRow>
            <TableRow className="bg-surface-elevated">
              <TableHead className="sticky left-0 top-10 z-30 bg-surface-elevated" />
              {columns.map((column) => (
                <TableHead
                  key={column.key}
                  className="sticky top-10 z-20 min-w-[130px] bg-surface-elevated text-right"
                  title={`${column.metricId} v${column.version}`}
                >
                  <div>{metricLabel(column.metricId)}</div>
                  <div className="font-mono text-[10px] font-normal text-text-tertiary">
                    v{column.version}
                  </div>
                </TableHead>
              ))}
            </TableRow>
            <StatisticRow statistic="computed" columns={columns} metrics={metrics} />
            <StatisticRow statistic="mean" columns={columns} metrics={metrics} />
            <StatisticRow statistic="median" columns={columns} metrics={metrics} />
          </TableHeader>
          <TableBody>
            {cases.map((caseItem, index) => (
              <TableRow
                key={caseItem.case_execution_id}
                className="cursor-pointer"
                onClick={() => {
                  navigate(`/runs/${runId}/cases/${caseItem.case_id}`);
                }}
              >
                <TableCell className="sticky left-0 z-10 bg-surface">
                  <div className="flex items-center gap-2">
                    <div className="min-w-0">
                      <div className="font-medium text-text-primary">
                        Case {index + 1}
                      </div>
                      <div className="max-w-[180px] truncate font-mono text-xs text-text-tertiary">
                        {caseItem.case_id}
                      </div>
                    </div>
                    <Badge variant={statusVariant(caseItem.status)}>
                      {caseItem.status.replaceAll("_", " ").toLowerCase()}
                    </Badge>
                    <ChevronRight className="ml-auto h-4 w-4 text-text-tertiary" />
                  </div>
                </TableCell>
                {columns.map((column) => (
                  <TableCell key={column.key} className="text-right">
                    <CellValue
                      result={cellFor(caseItem, column, metrics)}
                      metricId={column.metricId}
                    />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
          <TableFooter>
            <StatisticRow statistic="min" columns={columns} metrics={metrics} bottom />
            <StatisticRow statistic="max" columns={columns} metrics={metrics} bottom />
          </TableFooter>
        </Table>
      </div>
      <div className="border-t border-border-default px-4 py-3 text-xs text-text-tertiary">
        Showing {cases.length} cases and {columns.length} metrics. Click a case for
        details.
        {aggregates.length > 0 && " Run aggregates are shown above the matrix."}
      </div>
    </TooltipProvider>
  );
}
