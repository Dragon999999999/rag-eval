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
  TestMetricInfo,
  TestMetricsInfo,
  MetricImportResult,
  RunStatusResponse,
} from "./test-types";

// Services
export { TestService, MetricService } from "./test-service";

// Hooks
export {
  testKeys,
  metricKeys,
  useTests,
  useTest,
  useTestMetrics,
  useTestValidation,
  useCreateTest,
  useUpdateTest,
  useDeleteTest,
  useValidateTest,
  usePlanTest,
  useRunTest,
  useRun,
  useRunStatus,
  useStartTestRun,
  usePauseRun,
  useResumeRun,
  useRecoverRun,
  useCancelRun,
  useSetTestMetrics,
  useSelectAllMetrics,
  useImportTestYaml,
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

export { TestEditor } from "./components/test-editor";
export { ActiveRunIndicator } from "./components/active-run-indicator";
export { MetricSelector } from "./components/metric-selector";
export { RunProgress } from "./components/run-progress";
export { SearchableResourceSelect } from "./components/searchable-resource-select";
export { TestValidationStatus } from "./components/test-validation-status";

// Pages
export { TestsPage } from "./pages/tests-page";
export { TestDetailPage } from "./pages/test-detail-page";
export { TestCreatePage } from "./pages/test-create-page";
export { TestEditPage } from "./pages/test-edit-page";
