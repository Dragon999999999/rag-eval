/**
 * Step 5: Review component.
 */
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Surface } from "@/components/layout/surface";
import { Spinner } from "@/components/ui/spinner";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreateTest, useValidateTest, usePlanTest } from "../use-tests";
import { formValuesToTestDefinition } from "../test-builder-form";
import type { UseFormReturn } from "react-hook-form";
import type { TestBuilderValues } from "../test-builder-form";

interface ReviewStepProps {
  form: UseFormReturn<TestBuilderValues>;
  onPrevious: () => void;
  onSave: (testId: string) => void;
  onSaveAndRun: (testId: string) => void;
}

export function ReviewStep({
  form,
  onPrevious,
  onSave,
  onSaveAndRun,
}: ReviewStepProps) {
  const createTest = useCreateTest();
  const validateTest = useValidateTest();
  const planTest = usePlanTest();

  const [isSaving, setIsSaving] = useState(false);
  const [validationResult, setValidationResult] = useState<{
    valid: boolean;
    errors: string[];
  } | null>(null);
  const [plan, setPlan] = useState<{
    estimated_cases: number;
    estimated_requests: number;
  } | null>(null);

  const formValues = form.getValues();

  const handleSubmit = async (runImmediately = false) => {
    setIsSaving(true);
    try {
      const formValues = form.getValues();

      // Validate first
      const validation = await validateTest.mutateAsync({
        name: formValues.name,
        target_id: formValues.target_id,
        benchmark_id: formValues.benchmark_id,
        metric_config_id: formValues.metric_config_name,
        execution_config: formValues.execution_config,
        seed: formValues.seed ?? null,
        tags: formValues.tags,
        metadata: formValues.metadata,
      });
      setValidationResult({ valid: validation.valid, errors: validation.errors });

      if (!validation.valid) {
        setIsSaving(false);
        return;
      }

      // Get execution plan
      const planResult = await planTest.mutateAsync({
        name: formValues.name,
        target_id: formValues.target_id,
        benchmark_id: formValues.benchmark_id,
        metric_config_id: formValues.metric_config_name,
        execution_config: formValues.execution_config,
        seed: formValues.seed ?? null,
        tags: formValues.tags,
        metadata: formValues.metadata,
      });
      setPlan({
        estimated_cases: planResult.estimated_cases,
        estimated_requests: planResult.estimated_requests,
      });

      // Create test definition
      const payload = formValuesToTestDefinition(formValues);
      const newTest = await createTest.mutateAsync(payload);

      if (runImmediately) {
        onSaveAndRun(newTest.test_definition_id);
      } else {
        onSave(newTest.test_definition_id);
      }
    } catch (error) {
      console.error("Failed to save test:", error);
    } finally {
      setIsSaving(false);
    }
  };

  const executionConfig = formValues.execution_config;
  const selectedMetrics = formValues.selected_metrics;
  const tags = formValues.tags;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-text-primary">
          Review Configuration
        </h2>
        <p className="text-sm text-text-tertiary">
          Review your test configuration before saving.
        </p>
      </div>

      {/* Basic Information */}
      <Surface className="p-4">
        <h3 className="mb-3 text-sm font-medium text-text-primary">
          Basic Information
        </h3>
        <div className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="review-name">Test Name</Label>
            <Input
              id="review-name"
              value={formValues.name}
              onChange={(e) => {
                form.setValue("name", e.target.value, { shouldValidate: true });
              }}
            />
            {!formValues.name && (
              <p className="text-destructive text-xs">Test name is required</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="review-description">Description (optional)</Label>
            <Textarea
              id="review-description"
              value={formValues.description ?? ""}
              onChange={(e) => {
                form.setValue("description", e.target.value || null, {
                  shouldValidate: true,
                });
              }}
              placeholder="Describe the purpose of this test..."
              rows={3}
            />
          </div>
        </div>
      </Surface>

      {/* Target and Benchmark */}
      <Surface className="p-4">
        <h3 className="mb-3 text-sm font-medium text-text-primary">
          Target & Benchmark
        </h3>
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <Label className="text-xs text-text-tertiary">Target</Label>
            <div className="mt-1 font-medium text-text-primary">
              Target: {formValues.target_id}
            </div>
          </div>

          <div>
            <Label className="text-xs text-text-tertiary">Benchmark</Label>
            <div className="mt-1 font-medium text-text-primary">
              Benchmark: {formValues.benchmark_id}
            </div>
          </div>
        </div>
      </Surface>

      {/* Metrics */}
      <Surface className="p-4">
        <h3 className="mb-3 text-sm font-medium text-text-primary">Metrics</h3>
        <div className="space-y-2">
          <div className="text-sm font-medium text-text-primary">
            {formValues.metric_config_name}
          </div>
          <div className="flex flex-wrap gap-1">
            {selectedMetrics.map((metricId) => (
              <span
                key={metricId}
                className="rounded bg-surface-hover px-1.5 py-0.5 text-xs text-text-tertiary"
              >
                {metricId}
              </span>
            ))}
          </div>
        </div>
      </Surface>

      {/* Execution Settings */}
      <Surface className="p-4">
        <h3 className="mb-3 text-sm font-medium text-text-primary">
          Execution Settings
        </h3>
        <div className="grid gap-3 md:grid-cols-3">
          <div>
            <Label className="text-xs text-text-tertiary">Concurrency</Label>
            <div className="mt-1 text-text-primary">{executionConfig.concurrency}</div>
          </div>
          <div>
            <Label className="text-xs text-text-tertiary">Timeout</Label>
            <div className="mt-1 text-text-primary">
              {executionConfig.timeout_per_request}s
            </div>
          </div>
          <div>
            <Label className="text-xs text-text-tertiary">Retries</Label>
            <div className="mt-1 text-text-primary">{executionConfig.retries}</div>
          </div>
          <div>
            <Label className="text-xs text-text-tertiary">Failure Policy</Label>
            <div className="mt-1 capitalize text-text-primary">
              {executionConfig.failure_policy}
            </div>
          </div>
          <div>
            <Label className="text-xs text-text-tertiary">Case Scope</Label>
            <div className="mt-1 capitalize text-text-primary">
              {formValues.case_scope?.mode ?? "all"}
            </div>
          </div>
          {formValues.case_scope?.mode === "sample" && (
            <div>
              <Label className="text-xs text-text-tertiary">Sample Size</Label>
              <div className="mt-1 text-text-primary">
                {formValues.case_scope.sample_size} cases
              </div>
            </div>
          )}
        </div>
      </Surface>

      {/* Tags */}
      {tags.length > 0 && (
        <Surface className="p-4">
          <h3 className="mb-3 text-sm font-medium text-text-primary">Tags</h3>
          <div className="flex flex-wrap gap-2">
            {tags.map((tag, index) => (
              <span
                key={index}
                className="border-border rounded border bg-surface px-1.5 py-0.5 text-xs text-text-tertiary"
              >
                {tag}
              </span>
            ))}
          </div>
        </Surface>
      )}

      {/* Validation Errors */}
      {validationResult && !validationResult.valid && (
        <Surface className="border-destructive p-4">
          <h3 className="text-destructive mb-2 text-sm font-medium">
            Validation Errors
          </h3>
          <ul className="text-destructive list-inside list-disc text-sm">
            {validationResult.errors.map((error, index) => (
              <li key={index}>{error}</li>
            ))}
          </ul>
        </Surface>
      )}

      {/* Execution Plan Estimate */}
      {plan && (
        <Surface className="p-4">
          <h3 className="mb-2 text-sm font-medium text-text-primary">
            Execution Estimate
          </h3>
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <Label className="text-xs text-text-tertiary">Estimated Cases</Label>
              <div className="mt-1 text-lg font-semibold text-text-primary">
                {plan.estimated_cases.toLocaleString()}
              </div>
            </div>
            <div>
              <Label className="text-xs text-text-tertiary">
                Estimated API Requests
              </Label>
              <div className="mt-1 text-lg font-semibold text-text-primary">
                {plan.estimated_requests.toLocaleString()}
              </div>
            </div>
          </div>
        </Surface>
      )}

      {/* Actions */}
      <div className="flex justify-between">
        <Button variant="secondary" onClick={onPrevious}>
          Back
        </Button>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              void handleSubmit(false);
            }}
            disabled={isSaving || !formValues.name}
          >
            {isSaving ? <Spinner size="sm" /> : "Save Test"}
          </Button>
          <Button
            onClick={() => {
              void handleSubmit(true);
            }}
            disabled={isSaving || !formValues.name}
          >
            {isSaving ? <Spinner size="sm" /> : "Save & Run"}
          </Button>
        </div>
      </div>
    </div>
  );
}
