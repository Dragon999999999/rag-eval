/**
 * Step 3: Metrics Configuration component.
 */
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import { Spinner } from "@/components/ui/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useMetrics } from "../use-tests";
import type { UseFormReturn } from "react-hook-form";
import type { TestBuilderValues } from "../test-builder-form";
import { formatMetricFullName, formatRequirements } from "../test-formatters";

interface MetricsStepProps {
  form: UseFormReturn<TestBuilderValues>;
  targetId: string;
  benchmarkId: string;
  onPrevious: () => void;
  onNext: () => void;
}

export function MetricsStep({
  form,
  targetId,
  benchmarkId,
  onPrevious,
  onNext,
}: MetricsStepProps) {
  const { data: metrics, isLoading, error } = useMetrics();

  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [compatibilityResults, setCompatibilityResults] = useState<
    Record<string, { compatible: boolean; reason?: string }>
  >({});

  const configName = form.watch("metric_config_name");
  const selectedMetrics = form.watch("selected_metrics");
  const mode = form.watch("mode");

  const setConfigName = (name: string) => {
    form.setValue("metric_config_name", name, {
      shouldValidate: true,
      shouldDirty: true,
    });
  };

  const toggleMetric = (metricId: string) => {
    const current = form.getValues("selected_metrics");
    const updated = current.includes(metricId)
      ? current.filter((id) => id !== metricId)
      : [...current, metricId];
    form.setValue("selected_metrics", updated, {
      shouldValidate: true,
      shouldDirty: true,
    });
  };

  const setMode = (newMode: "all_available" | "explicit") => {
    form.setValue("mode", newMode, { shouldValidate: true, shouldDirty: true });
  };

  // Check compatibility for all metrics
  useEffect(() => {
    if (!metrics || !targetId || !benchmarkId) return;

    // Mock capabilities - real impl would fetch from backend
    const results: Record<string, { compatible: boolean; reason?: string }> = {};
    metrics.forEach((metric) => {
      results[metric.metric_id] = { compatible: true }; // Simplified - real impl would check
    });

    setCompatibilityResults(results);
  }, [metrics, targetId, benchmarkId]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Surface>
          <div className="flex items-center justify-center py-12">
            <Spinner size="lg" />
          </div>
        </Surface>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="error">
        <AlertDescription>An error occurred while fetching metrics.</AlertDescription>
      </Alert>
    );
  }

  if (!metrics) {
    return null;
  }

  // Group metrics by category
  const categories = Array.from(new Set(metrics.map((m) => m.category ?? "Other")));
  const filteredMetrics =
    selectedCategory === "all"
      ? metrics
      : metrics.filter((m) => m.category === selectedCategory);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-text-primary">Configure Metrics</h2>
        <p className="text-sm text-text-tertiary">
          Select and configure the evaluation metrics to run.
        </p>
      </div>

      {/* Configuration name */}
      <Surface className="p-4">
        <div className="space-y-2">
          <Label htmlFor="config-name">Configuration Name</Label>
          <Input
            id="config-name"
            value={configName}
            onChange={(e) => { setConfigName(e.target.value); }}
            placeholder="e.g., Grounding + Answer Quality"
          />
        </div>
      </Surface>

      {/* Mode selection */}
      <Surface className="p-4">
        <div className="space-y-3">
          <Label>Selection Mode</Label>
          <div className="space-y-2">
            <label className="flex cursor-pointer items-center gap-2">
              <Checkbox
                checked={mode === "explicit"}
                onCheckedChange={() => { setMode("explicit"); }}
              />
              <div>
                <div className="font-medium text-text-primary">Explicit Selection</div>
                <div className="text-sm text-text-tertiary">
                  Choose specific metrics to run
                </div>
              </div>
            </label>

            <label className="flex cursor-pointer items-center gap-2">
              <Checkbox
                checked={mode === "all_available"}
                onCheckedChange={() => { setMode("all_available"); }}
              />
              <div>
                <div className="font-medium text-text-primary">All Available</div>
                <div className="text-sm text-text-tertiary">
                  Run all metrics compatible with target and dataset
                </div>
              </div>
            </label>
          </div>
        </div>
      </Surface>

      {/* Metric selection */}
      {mode === "explicit" && (
        <Surface className="p-0">
          <Tabs value={selectedCategory} onValueChange={setSelectedCategory}>
            <div className="border-border border-b px-4">
              <TabsList>
                <TabsTrigger value="all">All</TabsTrigger>
                {categories.map((category) => (
                  <TabsTrigger key={category} value={category}>
                    {category}
                  </TabsTrigger>
                ))}
              </TabsList>
            </div>

            <div className="max-h-[400px] overflow-y-auto p-4">
              {filteredMetrics.map((metric) => {
                const compat = compatibilityResults[metric.metric_id];
                const isCompatible = compat?.compatible ?? true;
                const isSelected = selectedMetrics.includes(metric.metric_id);

                return (
                  <div
                    key={metric.metric_id}
                    className={`mb-3 flex items-start gap-3 rounded-md border p-3 transition-colors ${
                      isSelected ? "border-accent bg-surface-hover" : "border-border"
                    } ${!isCompatible ? "opacity-50" : ""}`}
                  >
                    <Checkbox
                      checked={isSelected}
                      onCheckedChange={() => { toggleMetric(metric.metric_id); }}
                      disabled={!isCompatible}
                    />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-text-primary">
                          {formatMetricFullName(metric)}
                        </span>
                        {!isCompatible && (
                          <Badge variant="error" className="text-xs">
                            Incompatible
                          </Badge>
                        )}
                      </div>
                      <p className="mt-1 text-sm text-text-tertiary">
                        {metric.description}
                      </p>
                      <div className="mt-2 flex items-center gap-2">
                        <Badge variant="info" className="text-xs">
                          {metric.scope}
                        </Badge>
                        {metric.requirements.length > 0 && (
                          <span className="text-xs text-text-tertiary">
                            Requires: {formatRequirements(metric.requirements)}
                          </span>
                        )}
                      </div>
                      {!isCompatible && compat?.reason && (
                        <p className="text-destructive mt-2 text-xs">{compat.reason}</p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Tabs>
        </Surface>
      )}

      {mode === "all_available" && (
        <Surface className="p-4">
          <p className="text-sm text-text-secondary">
            All compatible metrics will be automatically selected based on the target's
            capabilities and dataset features.
          </p>
          <div className="mt-4 space-y-2">
            {metrics
              .filter((m) => compatibilityResults[m.metric_id]?.compatible)
              .map((metric) => (
                <div key={metric.metric_id} className="flex items-center gap-2">
                  <Checkbox checked disabled />
                  <span className="text-sm text-text-primary">
                    {formatMetricFullName(metric)}
                  </span>
                </div>
              ))}
          </div>
        </Surface>
      )}

      <div className="flex justify-between">
        <Button variant="secondary" onClick={onPrevious}>
          Back
        </Button>
        <Button onClick={onNext} disabled={!configName || selectedMetrics.length === 0}>
          Next: Execution Settings
        </Button>
      </div>
    </div>
  );
}
