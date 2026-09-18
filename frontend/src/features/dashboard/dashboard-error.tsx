/**
 * Error state for dashboard.
 *
 * Shows when dashboard data fails to load.
 */
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

interface DashboardErrorProps {
  onRetry: () => void;
}

export function DashboardError({ onRetry }: DashboardErrorProps) {
  return (
    <Alert variant="error" className="my-8">
      <AlertTitle>Unable to load dashboard</AlertTitle>
      <AlertDescription className="mt-2">
        <p className="text-sm text-text-secondary">
          There was a problem loading the evaluation overview. This could be due to a
          network issue or server error.
        </p>
        <Button variant="secondary" size="sm" onClick={onRetry} className="mt-3">
          Retry
        </Button>
      </AlertDescription>
    </Alert>
  );
}
