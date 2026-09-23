import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Activity } from "lucide-react";
import { isPersistentRunStatus, useRunStatus } from "../use-tests";
import { setActiveRun, useActiveRunReference } from "./active-run-store";
import { ProgressBar } from "@/components/ui/progress-bar";
import { runStatusLabel } from "./run-progress";

/** Persistent, unobtrusive entry point for a run whose editor is closed. */
export function ActiveRunIndicator() {
  const navigate = useNavigate();
  const reference = useActiveRunReference();
  const { data: progress } = useRunStatus(reference?.runId ?? "");

  useEffect(() => {
    if (reference && progress && !isPersistentRunStatus(progress.status))
      setActiveRun(null);
  }, [progress, reference]);

  if (!reference || !progress || !isPersistentRunStatus(progress.status)) return null;

  return (
    <button
      type="button"
      className="border-accent/50 fixed bottom-5 right-5 z-40 w-64 rounded-lg border bg-surface-elevated p-3 text-left shadow-2xl transition hover:border-accent"
      onClick={() => {
        navigate(`/tests/${reference.testId}`);
      }}
      aria-label={`Open active run for ${reference.testName}`}
    >
      <div className="flex items-center gap-2">
        <Activity className="h-4 w-4 animate-pulse text-accent" />
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-text-primary">
          {reference.testName}
        </span>
        <span className="text-xs text-text-tertiary">
          {runStatusLabel(progress.status)}
        </span>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <ProgressBar value={progress.progress_percent} className="h-1.5" />
        <span className="w-10 text-right text-xs text-text-secondary">
          {Math.round(progress.progress_percent)}%
        </span>
      </div>
    </button>
  );
}
