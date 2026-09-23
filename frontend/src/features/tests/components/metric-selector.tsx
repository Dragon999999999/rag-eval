import { useMemo, useRef } from "react";
import { Upload } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Surface } from "@/components/layout/surface";
import type { MetricImportResult, TestMetricsInfo } from "../test-types";

interface MetricSelectorProps {
  metrics: TestMetricsInfo | undefined;
  loading: boolean;
  selected: string[];
  onToggle: (metricId: string) => void;
  onSelectAll: () => void;
  onImport: (file: File) => void;
  importResult?: MetricImportResult;
  importing?: boolean;
}

function readableRequirement(requirement: string | Record<string, unknown>): string {
  if (typeof requirement === "string") {
    return requirement.toLowerCase().replaceAll("_", " ");
  }

  const candidate = requirement.name ?? requirement.requirement;
  const value = typeof candidate === "string" ? candidate : "requirement";
  return value.toLowerCase().replaceAll("_", " ");
}

/** Display every registered metric with availability-aware selection controls. */
export function MetricSelector({
  metrics,
  loading,
  selected,
  onToggle,
  onSelectAll,
  onImport,
  importResult,
  importing = false,
}: MetricSelectorProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const availableCount =
    metrics?.metrics.filter((metric) => metric.applicable).length ?? 0;
  const unavailableCount = (metrics?.metrics.length ?? 0) - availableCount;
  const grouped = useMemo(() => {
    const groups = new Map<string, TestMetricsInfo["metrics"]>();
    for (const metric of metrics?.metrics ?? []) {
      const group = metric.metric_id.split(".")[0] ?? "Other";
      groups.set(group, [...(groups.get(group) ?? []), metric]);
    }
    return [...groups.entries()];
  }, [metrics]);

  return (
    <Surface className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-text-primary">Metrics</h2>
          <p className="mt-1 text-xs text-text-tertiary">
            All registered metrics are shown. Only metrics applicable to this target and
            benchmark can be selected.
          </p>
          {metrics && metrics.metrics.length > 0 && (
            <p className="mt-2 text-xs text-text-secondary">
              {availableCount} available
              {unavailableCount > 0 && <> · {unavailableCount} unavailable</>}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="secondary"
            onClick={onSelectAll}
            disabled={loading}
          >
            Select all applicable
          </Button>
          <Button
            size="sm"
            variant="ghost"
            loading={importing}
            onClick={() => fileRef.current?.click()}
          >
            <Upload className="h-3.5 w-3.5" /> Import YAML
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept=".yaml,.yml,application/yaml"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onImport(file);
              event.target.value = "";
            }}
          />
        </div>
      </div>
      {loading && <p className="mt-4 text-sm text-text-tertiary">Loading metrics...</p>}
      {!loading && metrics && metrics.metrics.length === 0 && (
        <p className="mt-4 text-sm text-text-tertiary">
          No registered metrics were found.
        </p>
      )}
      <div className="mt-4 space-y-4">
        {grouped.map(([group, groupMetrics]) => (
          <div key={group}>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-tertiary">
              {group}
            </div>
            <div className="space-y-2">
              {groupMetrics.map((metric) => {
                const isSelected = selected.includes(metric.metric_id);
                const unavailable = !metric.applicable;
                return (
                  <div
                    key={`${metric.metric_id}:${metric.version}`}
                    aria-disabled={unavailable}
                    className={`rounded-md border p-3 transition-colors ${isSelected ? "border-accent bg-accent-subtle" : "border-border-default"} ${unavailable ? "bg-surface opacity-60" : "hover:border-border-strong"}`}
                  >
                    <div className="flex items-start gap-3">
                      <Checkbox
                        aria-label={`Select ${metric.metric_id}`}
                        checked={isSelected}
                        disabled={unavailable}
                        onCheckedChange={() => {
                          onToggle(metric.metric_id);
                        }}
                        className="mt-0.5"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-medium text-text-primary">
                            {metric.metric_id}
                          </span>
                          <Badge variant="info">v{metric.version}</Badge>
                          {unavailable && <Badge variant="warning">Unavailable</Badge>}
                        </div>
                        <p className="mt-1 text-xs text-text-tertiary">
                          {metric.description}
                        </p>
                        {unavailable && metric.unavailable_reason && (
                          <p className="mt-2 text-xs text-warning">
                            {metric.unavailable_reason}
                          </p>
                        )}
                        {metric.requirements.length > 0 && (
                          <p className="mt-2 text-xs text-text-tertiary">
                            Requires{" "}
                            {metric.requirements.map(readableRequirement).join(", ")}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      {metrics?.warnings.map((warning) => (
        <p key={warning} className="mt-3 text-xs text-warning">
          {warning}
        </p>
      ))}
      {importResult && (
        <div className="mt-4 rounded-md border border-border-default bg-surface p-3 text-xs">
          <p className="font-medium text-text-primary">YAML import applied</p>
          {(importResult.warnings.length > 0 ||
            importResult.ignored_metrics.length > 0 ||
            importResult.unavailable_metrics.length > 0) && (
            <div className="mt-2 space-y-1 text-warning">
              {importResult.warnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
              {importResult.ignored_metrics.map((metric) => (
                <p key={`ignored-${metric}`}>Ignored: {metric}</p>
              ))}
              {importResult.unavailable_metrics.map((metric) => (
                <p key={`unavailable-${metric}`}>Unavailable: {metric}</p>
              ))}
            </div>
          )}
          {(importResult.target_conflict || importResult.benchmark_conflict) && (
            <p className="mt-2 text-warning">
              The YAML contained a conflicting target or benchmark; the current
              selection was kept.
            </p>
          )}
        </div>
      )}
    </Surface>
  );
}
