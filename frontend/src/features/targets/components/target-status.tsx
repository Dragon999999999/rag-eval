/**
 * Target status badge component.
 *
 * Displays target connection status with appropriate styling.
 */
import { StatusBadge } from "@/components/ui/status-badge";
import type { TargetConnectionStatus } from "../target-types";

interface TargetStatusProps {
  status: TargetConnectionStatus;
  showDot?: boolean;
}

export function TargetStatus({ status, showDot = true }: TargetStatusProps) {
  const config = getStatusConfig(status);

  return (
    <StatusBadge status={config.variant} showDot={showDot}>
      {config.label}
    </StatusBadge>
  );
}

function getStatusConfig(status: TargetConnectionStatus): {
  variant: "success" | "error" | "warning" | "neutral";
  label: string;
} {
  switch (status) {
    case "connected":
      return { variant: "success", label: "Connected" };
    case "disconnected":
      return { variant: "error", label: "Disconnected" };
    case "testing":
      return { variant: "warning", label: "Testing" };
    case "configuration-error":
      return { variant: "error", label: "Config Error" };
    case "unknown":
    default:
      return { variant: "neutral", label: "Unknown" };
  }
}
