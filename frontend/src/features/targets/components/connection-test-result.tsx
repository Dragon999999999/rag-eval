import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { TargetStatus } from "./target-status";
import type { TargetConnectionInfo } from "../target-types";

export function ConnectionTestResult({
  connection,
}: {
  connection: TargetConnectionInfo;
}) {
  return (
    <Alert
      variant={
        connection.status === "connected"
          ? "success"
          : connection.status === "disconnected"
            ? "error"
            : "warning"
      }
    >
      <AlertTitle>
        <TargetStatus status={connection.status} />
      </AlertTitle>
      <AlertDescription>
        {connection.error ? (
          <pre className="mt-2 whitespace-pre-wrap text-xs">
            {JSON.stringify(connection.error, null, 2)}
          </pre>
        ) : connection.health ? (
          "The target reported a healthy response."
        ) : (
          "The target did not provide a verifiable health response."
        )}
      </AlertDescription>
    </Alert>
  );
}
