import { CheckCircle2, CircleAlert } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { StatusBadge } from "@/components/ui/status-badge";
import type { ValidationResult } from "../test-types";

interface TestValidationStatusProps {
  validation?: ValidationResult;
  loading?: boolean;
}

/** Shows the authoritative backend readiness result without reproducing its rules. */
export function TestValidationStatus({
  validation,
  loading = false,
}: TestValidationStatusProps) {
  if (loading) return <p className="text-sm text-text-tertiary">Checking readiness…</p>;
  if (!validation)
    return (
      <p className="text-sm text-text-tertiary">
        Readiness will appear after the test is loaded.
      </p>
    );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={validation.valid ? "success" : "warning"}>
          {validation.valid ? "Ready to run" : "Not configured / Incomplete"}
        </StatusBadge>
        <span className="text-xs text-text-tertiary">
          Status: {validation.configuration_status}
        </span>
      </div>
      {!validation.valid && (
        <Alert variant="warning">
          <CircleAlert className="mr-2 inline h-4 w-4" />
          <AlertDescription>
            <ul className="list-inside list-disc space-y-1">
              {validation.errors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
      {validation.valid && (
        <div className="flex items-center gap-2 text-xs text-success">
          <CheckCircle2 className="h-4 w-4" /> {validation.resolved_metric_ids.length}{" "}
          metric(s) resolved by the backend.
        </div>
      )}
      {validation.warnings.map((warning) => (
        <p key={warning} className="text-xs text-warning">
          {warning}
        </p>
      ))}
    </div>
  );
}
