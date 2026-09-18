/**
 * Test builder form schema and state management.
 *
 * Uses React Hook Form with Zod validation for the 5-step builder:
 * 1. Target Selection
 * 2. Dataset Selection
 * 3. Metrics Configuration
 * 4. Execution Settings
 * 5. Review
 */
import { z } from "zod";
import { useForm } from "react-hook-form";
import type { UseFormReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { TestDefinitionCreate } from "./test-types";

/**
 * Builder step enum for type-safe navigation.
 */
export enum BuilderStep {
  TARGET = 1,
  DATASET = 2,
  METRICS = 3,
  EXECUTION = 4,
  REVIEW = 5,
}

/**
 * Step metadata for UI display.
 */
export const STEP_METADATA: Record<
  BuilderStep,
  { title: string; description: string }
> = {
  [BuilderStep.TARGET]: {
    title: "Select Target",
    description: "Choose the target system to evaluate",
  },
  [BuilderStep.DATASET]: {
    title: "Select Dataset",
    description: "Choose the benchmark dataset",
  },
  [BuilderStep.METRICS]: {
    title: "Configure Metrics",
    description: "Select and configure evaluation metrics",
  },
  [BuilderStep.EXECUTION]: {
    title: "Execution Settings",
    description: "Configure concurrency, timeouts, and failure handling",
  },
  [BuilderStep.REVIEW]: {
    title: "Review",
    description: "Review and submit your test configuration",
  },
};

/**
 * Form schema for Step 1: Target Selection.
 */
const targetStepSchema = z.object({
  target_id: z.string({ required_error: "Target must be selected" }),
});

/**
 * Form schema for Step 2: Dataset Selection.
 */
const datasetStepSchema = z.object({
  benchmark_id: z.string({ required_error: "Dataset must be selected" }),
  case_scope: z
    .object({
      mode: z.enum(["all", "filtered", "sample"]),
      filters: z
        .object({
          tags: z.array(z.string()).optional(),
          difficulty: z.string().optional(),
          answerability: z.string().optional(),
        })
        .optional(),
      sample_size: z.number().min(1).optional(),
      seed: z.number().int().positive().optional(),
    })
    .optional(),
});

/**
 * Form schema for Step 3: Metrics Configuration.
 */
const metricsStepSchema = z.object({
  metric_config_name: z
    .string({ required_error: "Metric configuration name is required" })
    .min(1, "Name must be at least 1 character"),
  mode: z.enum(["all_available", "explicit"]).default("explicit"),
  selected_metrics: z.array(z.string()).min(1, "At least one metric must be selected"),
  metric_parameters: z.record(z.unknown()).default({}),
  judge_config: z.record(z.unknown()).default({}),
  retrieval_config: z.record(z.unknown()).default({}),
});

/**
 * Form schema for Step 4: Execution Settings.
 */
const executionStepSchema = z.object({
  execution_config: z
    .object({
      concurrency: z.number().int().positive().default(4),
      timeout_per_request: z.number().int().positive().default(30),
      retries: z.number().int().nonnegative().default(2),
      failure_policy: z.enum(["continue", "abort"]).default("continue"),
      store_raw_responses: z.boolean().default(false),
      store_traces: z.boolean().default(false),
      store_usage: z.boolean().default(false),
    })
    .default({
      concurrency: 4,
      timeout_per_request: 30,
      retries: 2,
      failure_policy: "continue",
    }),
  seed: z.number().int().positive().nullable().optional(),
  tags: z.array(z.string()).default([]),
});

/**
 * Form schema for Step 5: Review (name and description).
 */
const reviewStepSchema = z.object({
  name: z
    .string({ required_error: "Test name is required" })
    .min(1, "Name must be at least 1 character")
    .max(255, "Name must be less than 255 characters"),
  description: z.string().nullable().optional(),
});

/**
 * Combined schema for all steps.
 */
export const testBuilderSchema = z
  .object({
    ...targetStepSchema.shape,
    ...datasetStepSchema.shape,
    ...metricsStepSchema.shape,
    ...executionStepSchema.shape,
    ...reviewStepSchema.shape,
  })
  .merge(
    z.object({
      // Additional fields not tied to specific steps
      metadata: z.record(z.unknown()).default({}),
    })
  );

/**
 * Complete form values type.
 */
export type TestBuilderValues = z.infer<typeof testBuilderSchema>;

/**
 * Partial form values for individual steps.
 */
export type TargetStepValues = z.infer<typeof targetStepSchema>;
export type DatasetStepValues = z.infer<typeof datasetStepSchema>;
export type MetricsStepValues = z.infer<typeof metricsStepSchema>;
export type ExecutionStepValues = z.infer<typeof executionStepSchema>;
export type ReviewStepValues = z.infer<typeof reviewStepSchema>;

/**
 * Create a new test builder form instance.
 */
export function useTestBuilderForm(
  defaultValues?: Partial<TestBuilderValues>
): UseFormReturn<TestBuilderValues> {
  return useForm<TestBuilderValues>({
    resolver: zodResolver(testBuilderSchema),
    defaultValues: {
      // Target step
      target_id: "",
      // Dataset step
      benchmark_id: "",
      case_scope: { mode: "all" },
      // Metrics step
      metric_config_name: "",
      mode: "explicit",
      selected_metrics: [],
      metric_parameters: {},
      judge_config: {},
      retrieval_config: {},
      // Execution step
      execution_config: {
        concurrency: 4,
        timeout_per_request: 30,
        retries: 2,
        failure_policy: "continue",
        store_raw_responses: false,
        store_traces: false,
        store_usage: false,
      },
      seed: null,
      tags: [],
      // Review step
      name: "",
      description: null,
      // Additional
      metadata: {},
      ...defaultValues,
    },
    mode: "onChange",
    reValidateMode: "onChange",
  });
}

/**
 * Convert form values to TestDefinitionCreate payload.
 */
export function formValuesToTestDefinition(
  values: TestBuilderValues
): TestDefinitionCreate {
  return {
    name: values.name,
    description: values.description ?? null,
    target_id: values.target_id,
    benchmark_id: values.benchmark_id,
    metric_config_id: values.metric_config_name,
    execution_config: values.execution_config,
    seed: values.seed ?? null,
    tags: values.tags,
    metadata: values.metadata,
  };
}

/**
 * Convert TestDefinition to form values (for editing).
 */
export function testDefinitionToFormValues(test: {
  name: string;
  description?: string | null;
  target_id: string;
  benchmark_id: string;
  metric_config_id: string;
  execution_config?: Record<string, unknown>;
  seed?: number | null;
  tags?: string[];
  metadata?: Record<string, unknown>;
}): Partial<TestBuilderValues> {
  return {
    name: test.name,
    description: test.description ?? null,
    target_id: test.target_id,
    benchmark_id: test.benchmark_id,
    metric_config_name: test.metric_config_id,
    execution_config: {
      concurrency: test.execution_config?.concurrency ?? 4,
      timeout_per_request: test.execution_config?.timeout_per_request ?? 30,
      retries: test.execution_config?.retries ?? 2,
      failure_policy: test.execution_config?.failure_policy ?? "continue",
      store_raw_responses: test.execution_config?.store_raw_responses ?? false,
      store_traces: test.execution_config?.store_traces ?? false,
      store_usage: test.execution_config?.store_usage ?? false,
    },
    seed: test.seed ?? null,
    tags: test.tags ?? [],
    metadata: test.metadata ?? {},
  };
}

/**
 * Get the next step in the builder.
 */
export function getNextStep(currentStep: BuilderStep): BuilderStep | null {
  if (currentStep >= BuilderStep.REVIEW) return null;
  return (currentStep + 1);
}

/**
 * Get the previous step in the builder.
 */
export function getPreviousStep(currentStep: BuilderStep): BuilderStep | null {
  if (currentStep <= BuilderStep.TARGET) return null;
  return (currentStep - 1);
}

/**
 * Validate a specific step.
 */
export async function validateStep<T extends Record<string, unknown>>(
  values: T,
  schema: z.ZodSchema<T>
): Promise<{ valid: boolean; errors: Record<string, string> }> {
  const result = await schema.safeParseAsync(values);

  if (!result.success) {
    const errors: Record<string, string> = {};
    result.error.errors.forEach((err) => {
      const path = err.path.join(".");
      errors[path] = err.message;
    });
    return { valid: false, errors };
  }

  return { valid: true, errors: {} };
}
