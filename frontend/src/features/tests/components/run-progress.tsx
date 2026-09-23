import { Pause, Play, RotateCcw, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ProgressBar } from "@/components/ui/progress-bar";
import { StatusBadge } from "@/components/ui/status-badge";
import type { RunStatus, RunStatusResponse } from "../test-types";

export const terminalRunStatuses = new Set([
  "COMPLETED",
  "FAILED",
  "CANCELLED",
  "completed",
  "failed",
  "cancelled",
]);
export const activeRunStatuses = new Set([
  "PENDING",
  "QUEUED",
  "RUNNING",
  "PAUSING",
  "PAUSED",
  "INTERRUPTED",
  "pending",
  "queued",
  "running",
  "paused",
]);

export function runStatusLabel(status: RunStatus): string {
  return status
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./, (value) => value.toUpperCase());
}

function badgeStatus(
  status: RunStatus
): "success" | "warning" | "error" | "info" | "neutral" {
  if (status === "COMPLETED" || status === "completed") return "success";
  if (status === "FAILED" || status === "failed") return "error";
  if (
    status === "PAUSED" ||
    status === "PAUSING" ||
    status === "INTERRUPTED" ||
    status === "CANCELLED" ||
    status === "cancelled"
  )
    return "warning";
  return "info";
}

interface RunProgressProps {
  status?: RunStatus;
  progress?: RunStatusResponse | null;
  onPause?: () => void;
  onResume?: () => void;
  onRecover?: () => void;
  onCancel?: () => void;
  busy?: boolean;
}

/** Compact progress and lifecycle controls for the current run. */
export function RunProgress({
  status,
  progress,
  onPause,
  onResume,
  onRecover,
  onCancel,
  busy,
}: RunProgressProps) {
  const currentStatus = progress?.status ?? status;
  if (!currentStatus) return null;
  const percentage = progress?.progress_percent ?? 0;
  const canPause = currentStatus === "RUNNING" || currentStatus === "running";
  const canResume = currentStatus === "PAUSED" || currentStatus === "paused";
  const canRecover = currentStatus === "INTERRUPTED";
  const canCancel = activeRunStatuses.has(currentStatus);

  return (
    <div className="space-y-4 rounded-lg border border-border-default bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <StatusBadge status={badgeStatus(currentStatus)}>
            {runStatusLabel(currentStatus)}
          </StatusBadge>
          {progress?.status_reason && (
            <span className="text-xs text-text-tertiary">{progress.status_reason}</span>
          )}
        </div>
        <div className="flex gap-2">
          {canPause && onPause && (
            <Button size="sm" variant="secondary" onClick={onPause} disabled={busy}>
              <Pause className="h-3.5 w-3.5" /> Pause
            </Button>
          )}
          {canResume && onResume && (
            <Button size="sm" onClick={onResume} disabled={busy}>
              <Play className="h-3.5 w-3.5" /> Resume
            </Button>
          )}
          {canRecover && onRecover && (
            <Button size="sm" variant="secondary" onClick={onRecover} disabled={busy}>
              <RotateCcw className="h-3.5 w-3.5" /> Recover
            </Button>
          )}
          {canCancel && onCancel && (
            <Button size="sm" variant="danger" onClick={onCancel} disabled={busy}>
              <Square className="h-3.5 w-3.5" /> Cancel
            </Button>
          )}
        </div>
      </div>
      <div>
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="text-text-secondary">Case progress</span>
          <span className="font-medium text-text-primary">
            {progress
              ? `${String(progress.complete_cases + progress.failed_cases)} / ${String(progress.total_cases)}`
              : "Waiting for progress"}
          </span>
        </div>
        <ProgressBar value={percentage} className="h-2.5" />
        <div className="mt-2 flex justify-between text-xs text-text-tertiary">
          <span>{percentage.toFixed(1)}%</span>
          {progress && (
            <span>
              {progress.running_cases} running · {progress.pending_cases} pending ·{" "}
              {progress.failed_cases} failed
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
