/**
 * Connection test result display component.
 */
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import type { TargetConnectionTestResult } from "../target-types";

interface ConnectionTestResultProps {
  result: TargetConnectionTestResult;
}

export function ConnectionTestResult({ result }: ConnectionTestResultProps) {
  if (result.success) {
    return (
      <Alert variant="success" className="mt-4">
        <CheckCircle2 className="h-4 w-4" />
        <AlertTitle>Connection successful</AlertTitle>
        <AlertDescription className="space-y-2">
          <p>The target is reachable and responding correctly.</p>
          {result.response_time_ms && (
            <div className="flex items-center gap-4 text-sm">
              <span className="text-text-tertiary">Response time:</span>
              <Badge variant="success">{result.response_time_ms} ms</Badge>
            </div>
          )}
        </AlertDescription>
      </Alert>
    );
  }

  // Determine error icon based on category
  const getIcon = () => {
    switch (result.error_category) {
      case "AUTHENTICATION":
        return <AlertTriangle className="h-4 w-4 text-warning" />;
      case "CONNECTION":
        return <XCircle className="h-4 w-4 text-error" />;
      default:
        return <XCircle className="h-4 w-4 text-error" />;
    }
  };

  return (
    <Alert variant="error" className="mt-4">
      {getIcon()}
      <AlertTitle>Connection failed</AlertTitle>
      <AlertDescription className="space-y-2">
        <p>{result.error}</p>
        <div className="flex flex-wrap items-center gap-4 text-sm">
          {result.http_status && (
            <Badge variant="error">HTTP {result.http_status}</Badge>
          )}
          {result.error_code && (
            <span className="text-text-tertiary">Code: {result.error_code}</span>
          )}
          {result.error_category && (
            <span className="text-text-tertiary">
              Category: {result.error_category}
            </span>
          )}
        </div>
      </AlertDescription>
    </Alert>
  );
}
