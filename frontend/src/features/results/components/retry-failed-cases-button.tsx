import { useState } from "react";
import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRetryFailedCases } from "../use-runs";
import { canRetryFailedCases } from "../run-retry";

interface RetryFailedCasesButtonProps {
  runId: string;
  status: string | undefined;
  failedCases: number | null | undefined;
  label?: string;
  variant?: "primary" | "secondary" | "ghost" | "danger";
}

/** Render the shared action for retrying failed cases in a completed run. */
export function RetryFailedCasesButton({
  runId,
  status,
  failedCases,
  label = "Retry failed",
  variant = "primary",
}: RetryFailedCasesButtonProps) {
  const retry = useRetryFailedCases();
  const [error, setError] = useState<string | null>(null);
  const count = failedCases ?? 0;

  if (!canRetryFailedCases(status, failedCases)) return null;

  const handleRetry = async () => {
    if (
      !confirm(
        `Retry ${String(count)} failed case${count === 1 ? "" : "s"}? Completed cases will be preserved.`
      )
    ) {
      return;
    }

    setError(null);
    try {
      await retry.mutateAsync(runId);
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : "Unable to retry failed cases."
      );
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant={variant}
        size="sm"
        loading={retry.isPending}
        onClick={() => void handleRetry()}
      >
        {!retry.isPending && <RotateCcw className="h-3.5 w-3.5" />}
        {label} ({count})
      </Button>
      {error && (
        <span role="alert" className="text-xs text-error">
          {error}
        </span>
      )}
    </div>
  );
}
