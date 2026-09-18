/**
 * Targets feature exports.
 */
export { TargetsPage } from "./pages/targets-page";
export { TargetCreatePage } from "./pages/target-create-page";
export { TargetDetailPage } from "./pages/target-detail-page";
export { TargetEditPage } from "./pages/target-edit-page";

export { TargetList } from "./components/target-list";
export { TargetForm } from "./components/target-form";
export { CapabilityList } from "./components/capability-list";
export { ConnectionTestResult } from "./components/connection-test-result";
export { TargetStatus } from "./components/target-status";

export {
  useTargetList,
  useTarget,
  useCreateTarget,
  useUpdateTarget,
  useDeleteTarget,
  useTargetCapabilities,
  useRefreshCapabilities,
  useTestConnection,
  targetQueryKeys,
} from "./use-targets";

export { TargetService } from "./target-service";

export type {
  Target,
  TargetCreate,
  TargetUpdate,
  TargetCapabilities,
  TargetConnectionTestResult,
  TargetAdapterType,
  CorpusMode,
  TargetConnectionStatus,
  TargetAuthConfig,
  TargetFormState,
} from "./target-types";

export {
  formatAdapterType,
  formatCorpusMode,
  formatTargetEndpoint,
  formatRelativeTime,
  getConnectionStatus,
  getCapabilityBadges,
  isValidPythonTarget,
  isValidUrl,
} from "./target-formatters";
