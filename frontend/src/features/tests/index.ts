/**
 * Test/Evaluation Builder feature exports.
 */

// Types
export type {
  MetricRequirement,
  MetricScope,
  MetricDefinition,
  MetricConfig,
  ExecutionConfig,
  CaseScope,
  CaseFilter,
  TestDefinition,
  TestDefinitionCreate,
  TestDefinitionUpdate,
  TestDefinitionInfo,
  TestDefinitionPlan,
  CompatibilityIssue,
  CompatibilitySeverity,
  ValidationResult,
  RunStatus,
  EvaluationRunSummary,
  CreateRunRequest,
} from "./test-types";

// Services
export { TestService, MetricService } from "./test-service";

// Hooks
export {
  testKeys,
  metricKeys,
  useTests,
  useTest,
  useCreateTest,
  useUpdateTest,
  useDeleteTest,
  useValidateTest,
  usePlanTest,
  useRunTest,
  useRun,
  useTestRuns,
  useMetrics,
  useMetric,
  useMetricsByCategory,
  useMetricCompatibility,
  useGetOrCreateMetricConfig,
} from "./use-tests";

// Formatters
export {
  formatMetricScope,
  formatMetricName,
  formatMetricFullName,
  formatRunStatus,
  getRunStatusVariant,
  formatTestName,
  formatRunName,
  formatProgress,
  formatCompatibilitySeverity,
  getCompatibilitySeverityVariant,
  formatRequirements,
  formatExecutionConfig,
  formatRelativeTime,
  formatCaseCount,
  truncateText,
} from "./test-formatters";

// Builder
export {
  BuilderStep,
  STEP_METADATA,
  useTestBuilderForm,
  formValuesToTestDefinition,
  testDefinitionToFormValues,
  getNextStep,
  getPreviousStep,
  validateStep,
  type TestBuilderValues,
  type TargetStepValues,
  type DatasetStepValues,
  type MetricsStepValues,
  type ExecutionStepValues,
  type ReviewStepValues,
} from "./test-builder-form";

export { TestBuilder } from "./builder/test-builder";
export { TargetStep } from "./builder/target-step";
export { DatasetStep } from "./builder/dataset-step";
export { MetricsStep } from "./builder/metrics-step";
export { ExecutionStep } from "./builder/execution-step";
export { ReviewStep } from "./builder/review-step";

// Pages
export { TestsPage } from "./pages/tests-page";
export { TestDetailPage } from "./pages/test-detail-page";
export { TestCreatePage } from "./pages/test-create-page";
export { TestEditPage } from "./pages/test-edit-page";
