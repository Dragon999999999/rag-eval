import { StatusBadge } from "@/components/ui/status-badge";
import { formatTargetStatus, statusVariant } from "../target-formatters";

export function TargetStatus({ status }: { status: string | null | undefined }) {
  return (
    <StatusBadge status={statusVariant(status)} showDot>
      {formatTargetStatus(status)}
    </StatusBadge>
  );
}
