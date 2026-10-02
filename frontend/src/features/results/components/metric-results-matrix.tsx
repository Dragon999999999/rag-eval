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
import {
  formatMetricStatistic,
  formatMetricStatus,
  formatMetricValue,
  getMetricCatalogEntry,
  getMetricDisplayName,
  getMetricStatistics,
  isMetricStatisticAllowed,
} from "../run-formatters";
import type { MetricStatistic } from "../metric-catalog";
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

type Statistic = MetricStatistic;

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
  if (!isMetricStatisticAllowed(column.metricId, statistic)) return null;

  const values = numericValues(column, metrics).sort((a, b) => a - b);
  if (statistic === "count") {
    return metrics.filter(
      (item) =>
        item.metric_id === column.metricId &&
        item.metric_version === column.version &&
        item.status.toUpperCase() === "COMPUTED"
    ).length;
  }
  if (values.length === 0) return null;
  if (statistic === "sum") {
    return values.reduce((sum, value) => sum + value, 0);
  }
  if (statistic === "mean") {
    return values.reduce((sum, value) => sum + value, 0) / values.length;
  }
  if (statistic === "min") return values[0] ?? null;
  if (statistic === "max") return values.at(-1) ?? null;
  const percentile =
    statistic === "median" || statistic === "p50" ? 50 : statistic === "p95" ? 95 : 99;
  const position = (percentile / 100) * (values.length - 1);
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  if (lower === upper) return values[lower] ?? null;
  return (
    (values[lower] ?? 0) +
    ((values[upper] ?? 0) - (values[lower] ?? 0)) * (position - lower)
  );
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
  const label = formatMetricStatistic(statistic);
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
              : statistic === "count"
                ? value
                : formatMetricValue(value, column.metricId, statistic)}
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
      const family = getMetricCatalogEntry(column.metricId).family;
      grouped.set(family, [...(grouped.get(family) ?? []), column]);
    }
    return [...grouped.entries()];
  }, [columns]);
  const statistics = useMemo(
    () => getMetricStatistics(columns.map((column) => column.metricId)),
    [columns]
  );
  const topStatistics = statistics.filter(
    (statistic) => !["sum", "min", "max"].includes(statistic)
  );
  const bottomStatistics = statistics.filter((statistic) =>
    ["sum", "min", "max"].includes(statistic)
  );

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
                  title={`${getMetricDisplayName(column.metricId)} v${column.version}`}
                >
                  <div>{getMetricDisplayName(column.metricId)}</div>
                  <div className="font-mono text-[10px] font-normal text-text-tertiary">
                    v{column.version}
                  </div>
                </TableHead>
              ))}
            </TableRow>
            {topStatistics.map((statistic) => (
              <StatisticRow
                key={statistic}
                statistic={statistic}
                columns={columns}
                metrics={metrics}
              />
            ))}
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
          {bottomStatistics.length > 0 && (
            <TableFooter>
              {bottomStatistics.map((statistic) => (
                <StatisticRow
                  key={statistic}
                  statistic={statistic}
                  columns={columns}
                  metrics={metrics}
                  bottom
                />
              ))}
            </TableFooter>
          )}
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
