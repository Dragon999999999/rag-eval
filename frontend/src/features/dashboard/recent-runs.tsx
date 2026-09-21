/**
 * Recent runs table for dashboard.
 *
 * Shows a dense table of recent evaluation runs.
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
import { StatusBadge } from "@/components/ui/status-badge";
import { formatDuration, formatRelativeTime, formatPercent } from "@/lib/format";
import type { DashboardRunSummary, RunStatus } from "./dashboard-types";

interface RecentRunsProps {
  runs: DashboardRunSummary[];
}

export function RecentRuns({ runs }: RecentRunsProps) {
  if (runs.length === 0) {
    return null;
  }

  return (
    <section className="space-y-4">
      <h2 className="text-base font-medium text-text-primary">Recent Runs</h2>

      <div className="rounded-lg border border-border-default bg-surface">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[200px]">Test</TableHead>
              <TableHead>Target</TableHead>
              <TableHead>Benchmark</TableHead>
              <TableHead className="w-[100px]">Status</TableHead>
              <TableHead className="w-[100px] text-right">Result</TableHead>
              <TableHead className="w-[100px] text-right">Duration</TableHead>
              <TableHead className="w-[100px] text-right">Started</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {runs.map((run) => (
              <RecentRunRow key={run.runId} run={run} />
            ))}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}

interface RecentRunRowProps {
  run: DashboardRunSummary;
}

function RecentRunRow({ run }: RecentRunRowProps) {
  const statusMap: Record<
    RunStatus,
    "success" | "warning" | "error" | "info" | "neutral"
  > = {
    queued: "neutral",
    running: "info",
    completed: "success",
    failed: "error",
    cancelled: "neutral",
  };

  const keyResult = run.keyMetrics?.[0];

  return (
    <TableRow className="group">
      <TableCell>
        <Link
          to={`/runs/${run.runId}`}
          className="font-medium text-text-primary hover:text-accent"
        >
          {run.testName}
        </Link>
      </TableCell>
      <TableCell className="text-text-secondary">{run.targetName}</TableCell>
      <TableCell className="text-text-secondary">{run.datasetName}</TableCell>
      <TableCell>
        <StatusBadge status={statusMap[run.status]} showDot>
          {run.status.charAt(0).toUpperCase() + run.status.slice(1)}
        </StatusBadge>
      </TableCell>
      <TableCell className="text-right">
        {keyResult ? (
          <span className="font-medium text-text-primary">
            {typeof keyResult.value === "number"
              ? formatPercent(keyResult.value)
              : keyResult.value}
          </span>
        ) : (
          <span className="text-text-tertiary">—</span>
        )}
      </TableCell>
      <TableCell className="text-right text-text-secondary">
        {run.duration ? formatDuration(run.duration) : "—"}
      </TableCell>
      <TableCell className="text-right text-text-secondary">
        {formatRelativeTime(run.startedAt)}
      </TableCell>
    </TableRow>
  );
}
