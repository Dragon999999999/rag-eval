import { Check, Minus } from "lucide-react";
import { Surface } from "@/components/layout/surface";

export function CapabilityList({
  capabilities,
  onRefresh,
  refreshing = false,
}: {
  capabilities: Record<string, unknown>;
  onRefresh?: () => void;
  refreshing?: boolean;
}) {
  const entries = Object.entries(capabilities).filter(
    ([, value]) => typeof value === "boolean"
  );
  return (
    <Surface className="p-6">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-medium text-text-primary">
          Discovered capabilities
        </h3>
        {onRefresh && (
          <button
            type="button"
            className="text-sm text-accent hover:underline disabled:opacity-50"
            onClick={onRefresh}
            disabled={refreshing}
          >
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
        )}
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {entries.map(([key, value]) => (
          <div key={key} className="flex items-center gap-2 text-sm">
            {value ? (
              <Check className="h-4 w-4 text-success" />
            ) : (
              <Minus className="h-4 w-4 text-text-tertiary" />
            )}
            <span className={value ? "text-text-primary" : "text-text-tertiary"}>
              {key.replaceAll("_", " ")}
            </span>
          </div>
        ))}
      </div>
      <pre className="mt-4 max-h-64 overflow-auto rounded bg-surface-hover p-3 text-xs text-text-tertiary">
        {JSON.stringify(capabilities, null, 2)}
      </pre>
    </Surface>
  );
}
